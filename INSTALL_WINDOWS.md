# Installation - Windows

## Prerequisites

- **Windows 10/11** (64-bit)
- **Docker Desktop** for Windows
- **Python 3.11+** (from python.org, check "Add to PATH" during install)
- **Node.js 18+** (from nodejs.org)
- **FFmpeg** (see step below)
- **Git** (from git-scm.com)
- **CMake** (from cmake.org, or via Visual Studio)
- **Visual Studio 2022** with "Desktop development with C++" workload (for compiling whisper.cpp)
- **Ollama** for Windows, or an OpenRouter API key
- **Hugging Face account** with access to pyannote/speaker-diarization-3.1

### Optional: NVIDIA GPU acceleration

If you have an NVIDIA GPU with CUDA support, whisper.cpp can use it for faster transcription. Install the [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) before building whisper.cpp.

## Installation

### 1. Clone the repo

```powershell
git clone https://github.com/fltman/transcriber.git
cd transcriber
```

### 2. Install FFmpeg

Download from https://www.gyan.dev/ffmpeg/builds/ (get the "essentials" build), extract it, and add the `bin` folder to your system PATH.

Verify it works:

```powershell
ffmpeg -version
```

### 3. Build whisper.cpp

```powershell
git clone https://github.com/ggerganov/whisper.cpp.git ..\whisper.cpp
cd ..\whisper.cpp

# CPU only
cmake -B build
cmake --build build --config Release

# OR with CUDA (if you have an NVIDIA GPU)
cmake -B build -DWHISPER_CUDA=ON
cmake --build build --config Release

cd ..\transcriber
```

The binary will be at `..\whisper.cpp\build\bin\Release\whisper-cli.exe`.

### 4. Download Whisper models

```powershell
mkdir models

# Medium model (main transcription, higher quality)
curl -L -o models\kb_whisper_ggml_medium.bin https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin

# Small model (live transcription, faster)
curl -L -o models\kb_whisper_ggml_small.bin https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin
```

### 5. Start PostgreSQL and Redis

Make sure Docker Desktop is running, then:

```powershell
docker-compose up -d
```

This starts:
- PostgreSQL on port **5433**
- Redis on port **6380**

### 6. Create the .env file

Create a file named `.env` in the project root with this content:

```env
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

# Paths to whisper.cpp (adjust to your setup, use forward slashes)
WHISPER_CLI_PATH=../whisper.cpp/build/bin/Release/whisper-cli.exe
WHISPER_MODEL_PATH=./models/kb_whisper_ggml_medium.bin
WHISPER_SMALL_MODEL_PATH=./models/kb_whisper_ggml_small.bin

STORAGE_PATH=./storage

# Hugging Face token (needed for pyannote.audio speaker diarization)
# Get yours at https://huggingface.co/settings/tokens
# You must accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1
HF_AUTH_TOKEN=hf_your_token_here
```

Edit the file and fill in your actual paths and tokens.

### 7. Set up the Python backend

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Note**: Installing PyTorch, pyannote.audio and SpeechBrain may take a while and download several GB of model files on first run.

If you have an NVIDIA GPU, install the CUDA version of PyTorch first:

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

### 8. Set up the frontend

```powershell
cd frontend
npm install
cd ..
```

### 9. Set up Ollama (if using local LLM)

Download and install Ollama from https://ollama.com, then:

```powershell
ollama pull qwen3:8b
```

## Running

Open **four separate terminals** (PowerShell or Command Prompt):

```powershell
# Terminal 1 - Backend API
venv\Scripts\activate
uvicorn main:app --port 8000 --reload

# Terminal 2 - Celery worker
venv\Scripts\activate
celery -A tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 3 - Frontend
cd frontend
npm run dev

# Terminal 4 - Ollama (if using local LLM, skip if already running)
ollama serve
```

Open **http://localhost:5174** in your browser.

## Troubleshooting

### "No module named 'pyannote'" or torch errors
Make sure you activated the virtual environment (`venv\Scripts\activate`) before running.

### Celery won't start
On Windows, Celery requires the `--pool=solo` flag (which is already in the command above). The default prefork pool does not work on Windows.

### whisper-cli not found
Check that the path in your `.env` file points to the correct location. On Windows, the Release build goes into a `Release` subfolder.

### Docker containers won't start
Make sure Docker Desktop is running and WSL 2 is enabled. Check with `docker ps`.

### Slow first run
The first transcription downloads pyannote and SpeechBrain model files (several GB). Subsequent runs use cached models.
