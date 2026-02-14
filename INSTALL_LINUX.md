# Installation - Linux

## Quick install

```bash
git clone https://github.com/fltman/transcriber.git
cd transcriber
bash install.sh   # Automated installer
bash start.sh     # Start all services
```

The script handles everything below automatically. Read on if you prefer manual setup or need to troubleshoot.

## Prerequisites

- **Ubuntu 22.04+**, Debian 12+, or similar (other distros work with adjusted package commands)
- **Docker** and **Docker Compose**
- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg**
- **CMake** and **build-essential**
- **Ollama**, or an OpenRouter API key
- **Hugging Face account** with access to pyannote/speaker-diarization-3.1

### Optional: NVIDIA GPU acceleration

If you have an NVIDIA GPU, install the [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) and NVIDIA drivers for faster transcription. Without a GPU, whisper.cpp runs on CPU (slower but works fine).

## Installation

### 1. Install system dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y git build-essential cmake ffmpeg python3 python3-venv python3-pip curl

# Fedora
sudo dnf install -y git gcc-c++ cmake ffmpeg python3 python3-pip curl

# Arch
sudo pacman -S git base-devel cmake ffmpeg python python-pip curl
```

Install Node.js 18+ (if not already installed):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Clone the repo

```bash
git clone https://github.com/fltman/transcriber.git
cd transcriber
```

### 3. Build whisper.cpp

```bash
git clone https://github.com/ggerganov/whisper.cpp.git ../whisper.cpp
cd ../whisper.cpp

# CPU only
cmake -B build
cmake --build build --config Release

# OR with CUDA (if you have an NVIDIA GPU)
# cmake -B build -DWHISPER_CUDA=ON
# cmake --build build --config Release

cd ../transcriber
```

The binary will be at `../whisper.cpp/build/bin/whisper-cli`.

### 4. Download Whisper models

```bash
mkdir -p models

# Medium model (main transcription, higher quality)
curl -L -o models/kb_whisper_ggml_medium.bin \
  https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin

# Small model (live transcription, faster)
curl -L -o models/kb_whisper_ggml_small.bin \
  https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin
```

### 5. Start PostgreSQL and Redis

```bash
docker compose up -d
```

This starts:
- PostgreSQL on port **5433**
- Redis on port **6380**

Verify they're running:

```bash
docker compose ps
```

### 6. Create the .env file

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

### 7. Set up the Python backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If you have an NVIDIA GPU, install the CUDA version of PyTorch first:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

**Note**: First install downloads several GB of model files for pyannote.audio and SpeechBrain.

### 8. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 9. Set up Ollama (if using local LLM)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
```

## Running

Start all four services. Use separate terminals or a terminal multiplexer like tmux:

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

### Running with tmux (all in one terminal)

```bash
tmux new-session -d -s transcriber

# Backend
tmux send-keys 'source venv/bin/activate && uvicorn main:app --port 8000 --reload' Enter

# Celery
tmux split-window -v
tmux send-keys 'source venv/bin/activate && celery -A tasks.celery_app worker --loglevel=info --pool=solo' Enter

# Frontend
tmux split-window -v
tmux send-keys 'cd frontend && npm run dev' Enter

# Ollama
tmux split-window -v
tmux send-keys 'ollama serve' Enter

tmux select-layout tiled
tmux attach -t transcriber
```

## Troubleshooting

### Permission denied on Docker
Add your user to the docker group:

```bash
sudo usermod -aG docker $USER
# Log out and back in for it to take effect
```

### pyannote.audio fails to install
Make sure you have Python 3.11+. On Ubuntu 22.04, you may need:

```bash
sudo apt install python3.11 python3.11-venv
python3.11 -m venv venv
```

### No audio in live recording
Your browser needs microphone permission. If running on a headless server, you'll need to access it via HTTPS or localhost.

### Slow transcription without GPU
CPU-only transcription with the medium model can take 2-5x the audio length. Consider using the small model (edit `WHISPER_MODEL_PATH` in `.env`) for faster results, or use a machine with an NVIDIA GPU.

### Celery worker crashes
Check that Redis is running (`docker compose ps`) and that the `REDIS_URL` in `.env` is correct.

### Slow first run
The first transcription downloads pyannote and SpeechBrain model files (several GB). Subsequent runs use cached models.
