# Transcriber

AI-powered local meeting transcription with automatic speaker identification. Upload an audio file, record in the browser, or run a live session - and get a full transcript with speakers identified by name.

![Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Stack](https://img.shields.io/badge/whisper.cpp-000?style=flat)
![Stack](https://img.shields.io/badge/pyannote.audio-orange?style=flat)

## How it works

1. **Upload, record, or go live** through the web UI
2. **Audio extraction** - FFmpeg converts to 16kHz mono WAV
3. **Transcription** - whisper.cpp with KB-LAB Swedish models (Metal GPU accelerated)
4. **Speaker diarization** - pyannote.audio 3.1 separates speakers
5. **Intro analysis** - LLM iteratively reads the transcript to detect introductions and count speakers
6. **Speaker identification** - Names matched to voices using LLM reasoning + SpeechBrain voice embeddings
7. **Results** - Color-coded transcript synced with audio playback, editable segments, AI-powered actions, export to 7 formats

See [FEATURES.md](FEATURES.md) for a complete feature list.

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

## Platform guides

The instructions below are for **macOS with Apple Silicon**. For other platforms:
- [Windows installation guide](INSTALL_WINDOWS.md)
- [Linux installation guide](INSTALL_LINUX.md)

## Prerequisites

- **macOS** with Apple Silicon (for Metal GPU acceleration)
- **Docker** and **Docker Compose**
- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (`brew install ffmpeg`)
- **whisper.cpp** compiled with Metal support
- **Ollama** with a model like `qwen3:8b` (recommended), or an OpenRouter API key
- **Hugging Face token** with access to `pyannote/speaker-diarization-3.1`

## Quick install

```bash
git clone https://github.com/fltman/transcriber.git
cd transcriber
bash install.sh   # macOS/Linux automated installer
bash start.sh     # Start all services
```

On Windows, use `install.ps1` and `start.ps1` instead (see [Windows guide](INSTALL_WINDOWS.md)).

The installer checks prerequisites, builds whisper.cpp, downloads models, sets up Python/Node dependencies, starts Docker, and creates the `.env` file. You only need to add your Hugging Face token afterwards.

## Manual installation

### 1. Clone the repo

```bash
git clone https://github.com/fltman/transcriber.git
cd transcriber
```

### 2. Build whisper.cpp with Metal support

```bash
git clone https://github.com/ggerganov/whisper.cpp.git ../whisper.cpp
cd ../whisper.cpp
cmake -B build -DWHISPER_METAL=ON
cmake --build build --config Release
cd ../transcriber
```

### 3. Download Whisper models

Download the KB-LAB Swedish GGML models:

```bash
mkdir -p models
# Medium model (main transcription, higher quality)
curl -L -o models/kb_whisper_ggml_medium.bin \
  https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin

# Small model (live transcription, faster)
curl -L -o models/kb_whisper_ggml_small.bin \
  https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin
```

### 4. Start PostgreSQL and Redis

```bash
docker-compose up -d
```

This starts:
- PostgreSQL on port **5433**
- Redis on port **6380**

### 5. Create the .env file

```bash
cat > .env << 'EOF'
DATABASE_URL=postgresql://transcriber:transcriber@localhost:5433/transcriber
REDIS_URL=redis://localhost:6380/0

# LLM provider: "ollama" or "openrouter"
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Alternative: OpenRouter (uncomment and fill in)
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=your_key_here
# OPENROUTER_MODEL=anthropic/claude-sonnet-4

# Paths to whisper.cpp (adjust to your setup)
WHISPER_CLI_PATH=../whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=./models/kb_whisper_ggml_medium.bin
WHISPER_SMALL_MODEL_PATH=./models/kb_whisper_ggml_small.bin

STORAGE_PATH=./storage

# Hugging Face token (needed for pyannote.audio speaker diarization)
# Get yours at https://huggingface.co/settings/tokens
# You must accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1
HF_AUTH_TOKEN=hf_your_token_here
EOF
```

Edit the file and fill in your actual paths and tokens.

### 6. Set up the Python backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 8. Set up Ollama (if using local LLM)

```bash
# Install Ollama from https://ollama.com
ollama pull qwen3:8b
```

## Running

Start all services. You need **four terminals** (or use `&` to background them):

```bash
# Terminal 1 - Backend API
source venv/bin/activate
uvicorn main:app --port 8000 --reload

# Terminal 2 - Celery worker (background processing)
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
2. Choose **Upload**, **Record**, or **Live**
   - **Upload**: drag-and-drop or browse for an audio/video file
   - **Record**: select your microphone (or system audio) and record
   - **Live**: start a real-time transcription session
3. Enter a title and click **Start**
4. For uploaded files, click **Start transcription** on the meeting page
5. Watch real-time progress as the pipeline runs
6. Browse the transcript with synced audio playback
7. Click speaker names to rename, click segments to edit text
8. Run **Actions** (summarize, action items, etc.) from the sidebar
9. **Export** to SRT, WebVTT, TXT, Markdown, JSON, DOCX, or PDF

## Project structure

```
transcriber/
├── main.py                    # FastAPI app entry point
├── config.py                  # Pydantic settings
├── database.py                # SQLAlchemy + migrations
├── model_config.py            # Model preset manager
├── docker-compose.yml         # PostgreSQL + Redis
├── model_presets/             # AI model configurations
├── api/
│   ├── meetings.py            # Upload, CRUD, process
│   ├── live_websocket.py      # Live transcription WebSocket
│   ├── speakers.py            # Rename, merge speakers
│   ├── segments.py            # Edit transcript text
│   ├── export.py              # 7-format export
│   ├── actions.py             # Custom LLM actions
│   ├── encryption.py          # Encrypt/decrypt meetings
│   └── model_settings.py      # Model preset API
├── services/
│   ├── audio_service.py       # FFmpeg extraction
│   ├── whisper_service.py     # whisper-cli wrapper
│   ├── diarization_service.py # pyannote pipeline
│   ├── embedding_service.py   # SpeechBrain ECAPA-TDNN
│   ├── speaker_id_service.py  # Name matching logic
│   ├── llm_service.py         # Ollama / OpenRouter
│   └── encryption_service.py  # Fernet encryption
├── tasks/
│   ├── celery_app.py          # Celery config
│   ├── process_meeting.py     # Main transcription pipeline
│   ├── action_task.py         # LLM action execution
│   ├── polish_task.py         # Live speaker refinement
│   ├── finalize_task.py       # Live post-processing
│   └── shared.py              # Shared task utilities
├── models/                    # SQLAlchemy models
│   ├── meeting.py
│   ├── speaker.py
│   ├── segment.py
│   ├── job.py
│   └── action.py
└── frontend/                  # React + TypeScript
    └── src/
        ├── App.tsx
        ├── store.ts           # Zustand state
        ├── pages/
        │   ├── HomePage.tsx
        │   └── MeetingPage.tsx
        ├── components/
        │   ├── TranscriptView.tsx
        │   ├── SpeakerPanel.tsx
        │   ├── AudioPlayer.tsx
        │   ├── AudioSourceSelect.tsx
        │   ├── ActionsPanel.tsx
        │   ├── ProgressTracker.tsx
        │   ├── ExportDialog.tsx
        │   ├── EncryptDialog.tsx
        │   ├── DecryptDialog.tsx
        │   ├── LiveRecordingBar.tsx
        │   └── SettingsDialog.tsx
        └── hooks/
            └── useLiveRecording.ts
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI, SQLAlchemy, Celery |
| Transcription | whisper.cpp with KB-LAB Swedish models |
| Diarization | pyannote.audio 3.1 |
| Voice embeddings | SpeechBrain ECAPA-TDNN |
| LLM | Ollama (qwen3:8b) or OpenRouter (Claude Sonnet 4) |
| Infrastructure | PostgreSQL, Redis, Docker Compose |
| Media | FFmpeg |

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/meetings` | Upload audio file |
| `POST` | `/api/meetings/live` | Create live session |
| `GET` | `/api/meetings` | List meetings |
| `GET` | `/api/meetings/{id}` | Get meeting with transcript |
| `DELETE` | `/api/meetings/{id}` | Delete meeting |
| `POST` | `/api/meetings/{id}/process` | Start transcription pipeline |
| `GET` | `/api/meetings/{id}/audio` | Stream audio |
| `GET` | `/api/meetings/{id}/export?format=srt` | Export transcript |
| `PUT` | `/api/segments/{id}` | Edit segment text |
| `PUT` | `/api/speakers/{id}` | Rename/recolor speaker |
| `POST` | `/api/speakers/merge` | Merge two speakers |
| `GET` | `/api/actions` | List actions |
| `POST` | `/api/actions` | Create custom action |
| `POST` | `/api/actions/{id}/run` | Run action on meeting |
| `GET` | `/api/actions/results/{id}/export` | Export action result |
| `POST` | `/api/meetings/{id}/encrypt` | Encrypt meeting |
| `POST` | `/api/meetings/{id}/decrypt` | Decrypt meeting |
| `GET` | `/api/model-settings/presets` | List model presets |
| `GET` | `/api/model-settings/assignments` | Get model assignments |
| `PUT` | `/api/model-settings/assignments` | Update model assignments |
| `WS` | `/ws/meetings/{id}` | Progress updates |
| `WS` | `/ws/live/{id}` | Live transcription stream |

## License

MIT
