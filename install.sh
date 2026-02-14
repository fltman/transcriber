#!/usr/bin/env bash
set -e

# Transcriber installer for macOS and Linux
# Usage: bash install.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo ""
echo "========================================"
echo "  Transcriber - Automated Installer"
echo "========================================"
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  *)      fail "Unsupported OS: $OS" ;;
esac
info "Detected platform: $PLATFORM"

# -------------------------------------------
# Step 1: Check prerequisites
# -------------------------------------------
echo ""
info "Checking prerequisites..."

MISSING=""

command -v git    >/dev/null 2>&1 || MISSING="$MISSING git"
command -v python3 >/dev/null 2>&1 || MISSING="$MISSING python3"
command -v node   >/dev/null 2>&1 || MISSING="$MISSING node"
command -v npm    >/dev/null 2>&1 || MISSING="$MISSING npm"
command -v cmake  >/dev/null 2>&1 || MISSING="$MISSING cmake"
command -v ffmpeg >/dev/null 2>&1 || MISSING="$MISSING ffmpeg"
command -v docker >/dev/null 2>&1 || MISSING="$MISSING docker"

if [ -n "$MISSING" ]; then
  echo ""
  warn "Missing required tools:$MISSING"
  echo ""
  if [ "$PLATFORM" = "macos" ]; then
    echo "  Install with Homebrew:"
    echo "    brew install$MISSING"
  else
    echo "  Install with your package manager, e.g.:"
    echo "    sudo apt install$MISSING"
  fi
  echo ""
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# Check Python version
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
  warn "Python 3.11+ recommended, found $PY_VERSION"
else
  ok "Python $PY_VERSION"
fi

# Check Node version
NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ "${NODE_VERSION:-0}" -lt 18 ]; then
  warn "Node.js 18+ recommended, found $(node -v 2>/dev/null || echo 'none')"
else
  ok "Node.js $(node -v)"
fi

ok "Prerequisites check done"

# -------------------------------------------
# Step 2: Build whisper.cpp
# -------------------------------------------
echo ""
WHISPER_DIR="$(dirname "$(pwd)")/whisper.cpp"

if [ -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
  ok "whisper.cpp already built at $WHISPER_DIR"
else
  info "Building whisper.cpp..."

  if [ ! -d "$WHISPER_DIR" ]; then
    git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR"
  fi

  cd "$WHISPER_DIR"

  if [ "$PLATFORM" = "macos" ]; then
    cmake -B build -DWHISPER_METAL=ON
  else
    # Check for NVIDIA GPU
    if command -v nvidia-smi >/dev/null 2>&1; then
      info "NVIDIA GPU detected, building with CUDA"
      cmake -B build -DWHISPER_CUDA=ON
    else
      info "No NVIDIA GPU detected, building CPU-only"
      cmake -B build
    fi
  fi

  cmake --build build --config Release -j "$(nproc 2>/dev/null || sysctl -n hw.ncpu)"
  cd - >/dev/null

  if [ -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
    ok "whisper.cpp built successfully"
  else
    fail "whisper.cpp build failed"
  fi
fi

# -------------------------------------------
# Step 3: Download Whisper models
# -------------------------------------------
echo ""
mkdir -p models

if [ -f "models/kb_whisper_ggml_medium.bin" ]; then
  ok "Medium model already downloaded"
else
  info "Downloading KB-LAB Swedish medium model (~1.5 GB)..."
  curl -L --progress-bar -o models/kb_whisper_ggml_medium.bin \
    https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin
  ok "Medium model downloaded"
fi

if [ -f "models/kb_whisper_ggml_small.bin" ]; then
  ok "Small model already downloaded"
else
  info "Downloading KB-LAB Swedish small model (~500 MB)..."
  curl -L --progress-bar -o models/kb_whisper_ggml_small.bin \
    https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin
  ok "Small model downloaded"
fi

# -------------------------------------------
# Step 4: Start Docker services
# -------------------------------------------
echo ""
if docker compose ps --status running 2>/dev/null | grep -q "postgres"; then
  ok "Docker services already running"
else
  info "Starting PostgreSQL and Redis..."
  docker compose up -d
  ok "Docker services started"
fi

# -------------------------------------------
# Step 5: Python virtual environment
# -------------------------------------------
echo ""
if [ -d "venv" ]; then
  ok "Python venv already exists"
else
  info "Creating Python virtual environment..."
  python3 -m venv venv
  ok "Created venv"
fi

info "Installing Python dependencies (this may take a while)..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Python dependencies installed"

# -------------------------------------------
# Step 6: Frontend
# -------------------------------------------
echo ""
if [ -d "frontend/node_modules" ]; then
  ok "Frontend dependencies already installed"
else
  info "Installing frontend dependencies..."
  cd frontend
  npm install --silent
  cd ..
  ok "Frontend dependencies installed"
fi

# -------------------------------------------
# Step 7: Create .env file
# -------------------------------------------
echo ""
if [ -f ".env" ]; then
  ok ".env file already exists (not overwriting)"
else
  info "Creating .env file..."
  cat > .env << ENVEOF
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

WHISPER_CLI_PATH=$WHISPER_DIR/build/bin/whisper-cli
WHISPER_MODEL_PATH=./models/kb_whisper_ggml_medium.bin
WHISPER_SMALL_MODEL_PATH=./models/kb_whisper_ggml_small.bin

STORAGE_PATH=./storage

# Hugging Face token (needed for pyannote.audio speaker diarization)
# Get yours at https://huggingface.co/settings/tokens
# You must accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1
HF_AUTH_TOKEN=hf_your_token_here
ENVEOF
  ok ".env file created"
  warn "Edit .env and add your Hugging Face token before running!"
fi

# -------------------------------------------
# Step 8: Check for Ollama
# -------------------------------------------
echo ""
if command -v ollama >/dev/null 2>&1; then
  ok "Ollama is installed"
  if ollama list 2>/dev/null | grep -q "qwen3:8b"; then
    ok "qwen3:8b model is available"
  else
    info "Pulling qwen3:8b model..."
    ollama pull qwen3:8b && ok "Model pulled" || warn "Could not pull model. Run 'ollama pull qwen3:8b' manually."
  fi
else
  warn "Ollama not installed. Install from https://ollama.com or use OpenRouter instead."
fi

# -------------------------------------------
# Done
# -------------------------------------------
echo ""
echo "========================================"
echo -e "  ${GREEN}Installation complete!${NC}"
echo "========================================"
echo ""
echo "  Before first run, make sure to:"
echo "    1. Edit .env and set HF_AUTH_TOKEN"
echo "    2. Accept pyannote model terms at:"
echo "       https://huggingface.co/pyannote/speaker-diarization-3.1"
echo ""
echo "  To start the app, run:"
echo "    bash start.sh"
echo ""
echo "  Or start manually in 4 terminals:"
echo "    source venv/bin/activate && uvicorn main:app --port 8000 --reload"
echo "    source venv/bin/activate && celery -A tasks.celery_app worker --loglevel=info --pool=solo"
echo "    cd frontend && npm run dev"
echo "    ollama serve"
echo ""
echo "  Then open http://localhost:5174"
echo ""
