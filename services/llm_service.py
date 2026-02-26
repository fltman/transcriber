import json
import logging
import re

import requests

from config import settings

log = logging.getLogger(__name__)

CHUNK_SECONDS = 30
MAX_CHUNKS = 20  # Safety limit: 10 minutes max


class LLMService:
    def __init__(self, preset: dict | None = None):
        if preset and preset.get("provider"):
            self.provider = preset["provider"]
            self.model = preset.get("model")
        else:
            self.provider = settings.llm_provider  # "openrouter" or "ollama"
            self.model = None  # use defaults from config

    def _call(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Route to the configured LLM provider."""
        if self.provider == "ollama":
            return self._call_ollama(messages, max_tokens)
        return self._call_openrouter(messages, max_tokens)

    def _call_openrouter(self, messages: list[dict], max_tokens: int) -> str:
        from preferences import get_secret
        headers = {
            "Authorization": f"Bearer {get_secret('openrouter_api_key')}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model or settings.openrouter_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _call_ollama(self, messages: list[dict], max_tokens: int) -> str:
        payload = {
            "model": self.model or settings.ollama_model,
            "messages": messages,
            "stream": False,
            "think": False,  # Disable qwen3 thinking mode for speed
            "keep_alive": "30m",  # Keep model loaded during recording sessions
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens,
            },
        }
        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload, timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    def _parse_json(self, content: str):
        """Extract JSON from LLM response, handling markdown code blocks and think tags."""
        # Strip Qwen3-style <think>...</think> blocks
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Try raw parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Extract from markdown code blocks
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 3:
                block = parts[1]
                if block.startswith("json"):
                    block = block[4:]
                try:
                    return json.loads(block.strip())
                except json.JSONDecodeError:
                    pass

        # Last resort: find first JSON object or array in the string
        decoder = json.JSONDecoder()
        for match in re.finditer(r'[\[{]', content):
            try:
                obj, _ = decoder.raw_decode(content, match.start())
                return obj
            except json.JSONDecodeError:
                continue

        raise ValueError(f"No valid JSON found in LLM response: {content[:200]}")

    # ------------------------------------------------------------------
    # Iterative intro detection
    # ------------------------------------------------------------------

    def analyze_intro_iteratively(
        self,
        whisper_segments: list[dict],
        on_progress: callable = None,
    ) -> dict:
        """
        Send transcript to LLM in ~30s chunks. After each chunk, ask if the
        introduction phase is still ongoing. Stop when the LLM says it's done.

        Returns:
            {
                "speaker_count": int,
                "names": ["Anders", "Claude", ...],
                "intro_end_time": float,
            }
        """
        chunks = self._build_chunks(whisper_segments, CHUNK_SECONDS)

        if not chunks:
            return {"speaker_count": 0, "names": [], "intro_end_time": 0}

        messages = [
            {
                "role": "system",
                "content": (
                    "Du ar en motesanalytiker. Du far en transkribering av ett mote "
                    "i omgangar (chunk for chunk). Din uppgift ar att identifiera "
                    "presentationsfasen - den del dar deltagarna presenterar sig. "
                    "For varje ny chunk, analysera om presentationerna fortfarande pagar "
                    "eller om motet har gatt vidare till annat innehall.\n\n"
                    "Svara ALLTID med JSON i exakt detta format:\n"
                    '{"intro_ongoing": true/false, '
                    '"speaker_count": <antal unika deltagare hittills>, '
                    '"names": ["namn1", "namn2"], '
                    '"reasoning": "kort forklaring"}'
                ),
            }
        ]

        result = {"speaker_count": 0, "names": [], "intro_end_time": 0}

        for i, chunk in enumerate(chunks):
            if i >= MAX_CHUNKS:
                break

            chunk_text = chunk["text"]
            chunk_end = chunk["end_time"]

            messages.append({
                "role": "user",
                "content": (
                    f"Chunk {i + 1} (tid {chunk['start_time']:.0f}s - {chunk_end:.0f}s):\n"
                    f"{chunk_text}\n\n"
                    f"Pagar presentationsfasen fortfarande? "
                    f"Hur manga unika deltagare har du identifierat hittills?"
                ),
            })

            if on_progress:
                on_progress(f"Analyserar chunk {i + 1}/{len(chunks)} ({chunk_end:.0f}s)...")

            try:
                response_text = self._call(messages, max_tokens=500)
                messages.append({"role": "assistant", "content": response_text})

                data = self._parse_json(response_text)
                log.info(f"Intro chunk {i+1}: {data}")

                result["speaker_count"] = data.get("speaker_count", result["speaker_count"])
                result["names"] = data.get("names", result["names"])
                result["intro_end_time"] = chunk_end

                if not data.get("intro_ongoing", True):
                    log.info(f"Intro ended at {chunk_end:.0f}s with {result['speaker_count']} speakers")
                    break

            except Exception as e:
                log.warning(f"LLM chunk {i+1} failed: {e}")
                continue

        return result

    def _build_chunks(self, segments: list[dict], chunk_seconds: float) -> list[dict]:
        """Group whisper segments into time-based chunks."""
        if not segments:
            return []

        chunks = []
        current_texts = []
        chunk_start = segments[0].get("start", 0)
        chunk_end = chunk_start

        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", seg_start)
            text = seg.get("text", "").strip()
            if not text:
                continue

            if seg_start - chunk_start >= chunk_seconds and current_texts:
                chunks.append({
                    "text": " ".join(current_texts),
                    "start_time": chunk_start,
                    "end_time": chunk_end,
                })
                current_texts = []
                chunk_start = seg_start

            current_texts.append(text)
            chunk_end = seg_end

        if current_texts:
            chunks.append({
                "text": " ".join(current_texts),
                "start_time": chunk_start,
                "end_time": chunk_end,
            })

        return chunks

    # ------------------------------------------------------------------
    # Speaker identification from labeled intro segments
    # ------------------------------------------------------------------

    def identify_speakers_from_intro(self, intro_text: str) -> list[dict]:
        """
        Send intro transcript (with speaker labels) to LLM to map names.
        Returns list of {speaker_label, name}.
        """
        prompt = f"""Analysera denna transkribering fran borjan av ett mote.
Identifiera vilka personer som presenterar sig och koppla deras namn till deras talaretiketter.

Transkribering:
{intro_text}

Svara ENBART med en JSON-array i detta format:
[
  {{"speaker_label": "SPEAKER_00", "name": "Fornamn Efternamn"}},
  {{"speaker_label": "SPEAKER_01", "name": "Fornamn Efternamn"}}
]

Om du inte kan identifiera nagra namn, svara med en tom array: []
Svara ENBART med JSON, ingen annan text."""

        try:
            content = self._call([{"role": "user", "content": prompt}])
            return self._parse_json(content)
        except Exception:
            return []
