# Features

## Core Transcription

- **File upload** - Drag-and-drop or browse for audio/video files (MP3, MP4, WAV, WebM, M4A)
- **Browser recording** - Record directly from the browser with real-time audio level visualization
- **Audio source selection** - Choose between available microphones or capture system/desktop audio via screen share
- **Live transcription** - Real-time WebSocket-based transcription that streams segments as you speak
- **Swedish speech recognition** - whisper.cpp with KB-LAB Swedish models, Metal GPU accelerated on Apple Silicon
- **Automatic audio extraction** - FFmpeg converts any input to 16kHz mono WAV

## Speaker Identification

- **Pyannote.audio 3.1 diarization** - Automatic speaker separation with configurable min/max speaker count
- **Intro-based identification** - LLM iteratively analyzes meeting introductions to extract speaker names
- **Voice embedding matching** - SpeechBrain ECAPA-TDNN embeddings with cosine similarity to map names to voices
- **Fallback labeling** - Speakers labeled as "Deltagare 1", "Deltagare 2" when no introductions are detected
- **Live speaker assignment** - Provisional centroid-based speaker detection during live recording
- **Polish passes** - Post-recording refinement with speaker merging and LLM-powered naming

## Transcript Editing

- **Inline text editing** - Click any segment to edit the transcription text
- **Speaker reassignment** - Move segments to a different speaker
- **Speaker renaming** - Rename any identified speaker
- **Speaker color customization** - Assign custom colors for visual differentiation
- **Speaker merging** - Merge two speakers into one, consolidating all segments
- **Original text preservation** - Tracks original vs. edited text

## Audio Playback

- **Synced playback** - Click any segment to jump to that point in the audio
- **Auto-scroll** - Transcript follows playback position automatically
- **Timestamps** - MM:SS timestamps displayed on each segment

## Export

- **SRT** - Subtitle format with timecodes and speaker labels
- **WebVTT** - Web video subtitle format with voice tags
- **Plain text** - Speaker-grouped transcript with section headers
- **Markdown** - Formatted with speaker headings and timestamps
- **JSON** - Structured data for programmatic use
- **DOCX** - Microsoft Word document with formatted headings
- **PDF** - Professional PDF with styled layout and metadata

## Actions (LLM Analysis)

- **Custom action library** - Create reusable LLM prompts (summarize, action items, etc.)
- **Run against any meeting** - Execute actions on completed transcripts
- **Result history** - Browse previous action results per meeting
- **Result export** - Download action results as TXT, MD, DOCX, or PDF
- **Real-time status** - WebSocket updates for running/completed/failed actions

## Encryption

- **Password protection** - Encrypt transcript segments with PBKDF2 key derivation + Fernet encryption
- **Optional action result encryption** - Choose to also encrypt action results
- **Unlock workflow** - Password verification before decryption
- **Visual indicators** - Lock icons on encrypted meetings

## Model Configuration

- **Preset system** - JSON-based model presets in `model_presets/` directory
- **Per-task assignment** - Different models for transcription, live transcription, analysis, and actions
- **Multiple LLM providers** - OpenRouter (Claude Sonnet 4, etc.) and local Ollama (Qwen 3 8B, Gemma 3, etc.)
- **Multiple Whisper models** - Medium (higher quality) and small (faster, for live) variants
- **Settings UI** - Configure model assignments from the web interface
- **Persistent settings** - Assignments saved to `storage/settings.json`

## Live Recording

- **WebSocket streaming** - Chunked audio sent to server every 4 seconds as complete WebM files
- **Real-time segments** - Transcription results appear as you speak
- **Recording bar** - Shows elapsed time, audio levels, and stop control
- **Auto-finalization** - Full-quality re-processing triggered automatically after recording stops
- **Progressive speaker refinement** - Speaker names improved in background polish passes

## UI

- **Meeting dashboard** - List of all meetings with status badges, duration, speaker count
- **Three input modes** - Upload, Record, Live tabs in the new transcription dialog
- **Real-time progress** - Step-by-step progress bar during processing
- **Dark theme** - Slate/violet dark UI throughout
- **Responsive layout** - Sidebar with speakers/actions, main transcript area

## Technical

- **FastAPI backend** with async WebSocket support
- **React + TypeScript + Vite** frontend with Zustand state management
- **PostgreSQL** for persistent storage
- **Redis + Celery** for background task processing
- **FFmpeg** for audio/video conversion
- **whisper.cpp** (native binary) for transcription
- **pyannote.audio** for diarization
- **SpeechBrain** for voice embeddings
