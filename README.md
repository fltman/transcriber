# Transcriber

AI-powered local meeting transcription with automatic speaker identification. Upload an audio file or record directly in the browser, and get a full transcript with speakers identified by name.

![Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Stack](https://img.shields.io/badge/whisper.cpp-000?style=flat)
![Stack](https://img.shields.io/badge/pyannote.audio-orange?style=flat)

## How it works

1. **Upload or record** an audio file through the web UI
2. **Audio extraction** - FFmpeg converts to 16kHz mono WAV
3. **Transcription** - whisper.cpp with KB-LAB Swedish models (Metal GPU accelerated)
4. **Speaker diarization** - pyannote.audio 3.1 separates speakers
5. **Intro analysis** - LLM iteratively reads the transcript to detect meeting introductions and count speakers
6. **Speaker identification** - Names are matched to voices using LLM reasoning + SpeechBrain voice embeddings
7. **Results** - Color-coded transcript synced with audio playback, editable segments, export to SRT/VTT/TXT/JSON

### Speaker identification models

- **Model 2 (primary)**: When the meeting starts with introductions ("My name is..."), the LLM extracts names and maps them to speaker embeddings using cosine similarity
- **Model 3 (fallback)**: When no introductions are detected, speakers are labeled as "Participant 1", "Participant 2", etc.

## Architecture

```
Browser ─── React/Vite ──┐
                         ├── FastAPI ─── Celery Worker ─── whisper.cpp (Metal GPU)
                         │      │              │
                         │   WebSocket     pyannote.audio
                         │   (progress)    SpeechBrain
                         │      │           LLM (Ollama/OpenRouter)
                         │      │
                     PostgreSQL  Redis
                      (data)   (queue + pubsub)
```

**Hybrid setup**: PostgreSQL and Redis run in Docker. Python backend and Celery worker run natively on macOS for Metal GPU access.

## Prerequisites

- **macOS** with Apple Silicon (for Metal GPU acceleration)
- **Docker** and **Docker Compose**
- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (`brew install ffmpeg`)
- **whisper.cpp** compiled with Metal support
- **Ollama** with `qwen3:8b` (recommended) or an OpenRouter API key
- **Hugging Face token** with access to `pyannote/speaker-diarization-3.1`

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/transcriber.git
cd transcriber
cp .env.example .env
# Edit .env with your paths and API keys
```

### 2. Environment variables

```env
DATABASE_URL=postgresql://transcriber:transcriber@localhost:5433/transcriber
REDIS_URL=redis://localhost:6380/0

# LLM provider: "ollama" (local) or "openrouter" (cloud)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Alternative: OpenRouter
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=your_key_here
# OPENROUTER_MODEL=anthropic/claude-sonnet-4

# Paths to whisper.cpp
WHISPER_CLI_PATH=/path/to/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=/path/to/kb_whisper_ggml_medium.bin

STORAGE_PATH=./storage
HF_AUTH_TOKEN=hf_your_token_here
```

### 3. Start infrastructure

```bash
docker-compose up -d
```

### 4. Python backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Frontend

```bash
cd frontend
npm install
```

### 6. Ollama (if using local LLM)

```bash
ollama pull qwen3:8b
```

## Running

Start all four services in separate terminals:

```bash
# Terminal 1 - Backend
source venv/bin/activate
uvicorn main:app --port 8001 --reload

# Terminal 2 - Celery worker
source venv/bin/activate
celery -A tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 3 - Frontend
cd frontend
npm run dev

# Terminal 4 - Ollama (if using local LLM)
ollama serve
```

Open **http://localhost:5174** in your browser.

## Usage

1. Click **New transcription** on the home page
2. Choose **Upload file** or **Record audio**
3. Enter a title and click **Start**
4. On the meeting page, click **Start transcription**
5. Watch real-time progress as the pipeline runs
6. When complete, browse the transcript with synced audio playback
7. Click speaker names to rename them, click segments to edit text
8. Export to SRT, WebVTT, plain text, or JSON

## Project structure

```
transcriber/
├── main.py                    # FastAPI app
├── config.py                  # Pydantic settings
├── database.py                # SQLAlchemy setup
├── ws_manager.py              # WebSocket manager
├── docker-compose.yml         # PostgreSQL + Redis
├── api/
│   ├── meetings.py            # Upload, CRUD, process
│   ├── speakers.py            # Rename, merge speakers
│   ├── segments.py            # Edit transcript text
│   ├── export.py              # SRT/VTT/TXT/JSON export
│   └── websocket.py           # Real-time progress
├── services/
│   ├── audio_service.py       # FFmpeg extraction
│   ├── whisper_service.py     # whisper-cli wrapper
│   ├── diarization_service.py # pyannote pipeline
│   ├── embedding_service.py   # SpeechBrain ECAPA-TDNN
│   ├── speaker_id_service.py  # Name matching logic
│   └── llm_service.py         # Ollama / OpenRouter
├── tasks/
│   ├── celery_app.py          # Celery config
│   └── process_meeting.py     # Pipeline orchestration
├── models/                    # SQLAlchemy models
│   ├── meeting.py
│   ├── speaker.py
│   ├── segment.py
│   └── job.py
└── frontend/                  # React + TypeScript
    └── src/
        ├── App.tsx
        ├── pages/
        │   ├── HomePage.tsx   # Upload & meeting list
        │   └── MeetingPage.tsx
        └── components/
            ├── TranscriptView.tsx
            ├── SpeakerPanel.tsx
            ├── AudioPlayer.tsx
            ├── ProgressTracker.tsx
            └── ExportDialog.tsx
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI, SQLAlchemy, Celery |
| Transcription | whisper.cpp with KB-LAB Swedish models |
| Diarization | pyannote.audio 3.1 |
| Voice embeddings | SpeechBrain ECAPA-TDNN |
| LLM | Ollama (qwen3:8b) or OpenRouter (Claude Sonnet) |
| Infrastructure | PostgreSQL, Redis, Docker Compose |
| Media | FFmpeg |

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/meetings` | Upload audio file |
| `GET` | `/api/meetings` | List meetings |
| `GET` | `/api/meetings/{id}` | Get meeting with transcript |
| `DELETE` | `/api/meetings/{id}` | Delete meeting |
| `POST` | `/api/meetings/{id}/process` | Start transcription pipeline |
| `GET` | `/api/meetings/{id}/audio` | Stream audio |
| `GET` | `/api/meetings/{id}/export?format=srt` | Export transcript |
| `PUT` | `/api/segments/{id}` | Edit segment text |
| `PUT` | `/api/speakers/{id}` | Rename speaker |
| `POST` | `/api/speakers/merge` | Merge two speakers |
| `WS` | `/ws/meetings/{id}` | Real-time progress updates |

## License

MIT
