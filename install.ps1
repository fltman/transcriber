# Transcriber installer for Windows
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

function Info($msg)  { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "========================================"
Write-Host "  Transcriber - Automated Installer"
Write-Host "========================================"
Write-Host ""

# -------------------------------------------
# Step 1: Check prerequisites
# -------------------------------------------
Info "Checking prerequisites..."

$missing = @()

if (-not (Get-Command git -ErrorAction SilentlyContinue))    { $missing += "git" }
if (-not (Get-Command python -ErrorAction SilentlyContinue))  { $missing += "python" }
if (-not (Get-Command node -ErrorAction SilentlyContinue))    { $missing += "node" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue))     { $missing += "npm" }
if (-not (Get-Command cmake -ErrorAction SilentlyContinue))   { $missing += "cmake" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue))  { $missing += "ffmpeg" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue))  { $missing += "docker" }

if ($missing.Count -gt 0) {
    Write-Host ""
    Warn "Missing required tools: $($missing -join ', ')"
    Write-Host ""
    Write-Host "  Install with winget:"
    foreach ($tool in $missing) {
        switch ($tool) {
            "git"    { Write-Host "    winget install Git.Git" }
            "python" { Write-Host "    winget install Python.Python.3.12" }
            "node"   { Write-Host "    winget install OpenJS.NodeJS.LTS" }
            "cmake"  { Write-Host "    winget install Kitware.CMake" }
            "ffmpeg" { Write-Host "    winget install Gyan.FFmpeg" }
            "docker" { Write-Host "    winget install Docker.DockerDesktop" }
        }
    }
    Write-Host ""
    $reply = Read-Host "Continue anyway? (y/N)"
    if ($reply -ne "y" -and $reply -ne "Y") { exit 1 }
}

# Check Python version
try {
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $pyMajor, $pyMinor = $pyVer -split '\.'
    if ([int]$pyMajor -lt 3 -or ([int]$pyMajor -eq 3 -and [int]$pyMinor -lt 11)) {
        Warn "Python 3.11+ recommended, found $pyVer"
    } else {
        Ok "Python $pyVer"
    }
} catch {
    Warn "Could not check Python version"
}

Ok "Prerequisites check done"

# -------------------------------------------
# Step 2: Build whisper.cpp
# -------------------------------------------
Write-Host ""
$whisperDir = Join-Path (Split-Path $PWD -Parent) "whisper.cpp"
$whisperBin = Join-Path $whisperDir "build\bin\Release\whisper-cli.exe"

if (Test-Path $whisperBin) {
    Ok "whisper.cpp already built"
} else {
    Info "Building whisper.cpp..."

    if (-not (Test-Path $whisperDir)) {
        git clone https://github.com/ggerganov/whisper.cpp.git $whisperDir
    }

    Push-Location $whisperDir

    # Check for NVIDIA GPU
    $hasNvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($hasNvidia) {
        Info "NVIDIA GPU detected, building with CUDA"
        cmake -B build -DWHISPER_CUDA=ON
    } else {
        Info "No NVIDIA GPU detected, building CPU-only"
        cmake -B build
    }

    cmake --build build --config Release
    Pop-Location

    if (Test-Path $whisperBin) {
        Ok "whisper.cpp built successfully"
    } else {
        Fail "whisper.cpp build failed. Make sure Visual Studio 2022 with C++ workload is installed."
    }
}

# -------------------------------------------
# Step 3: Download Whisper models
# -------------------------------------------
Write-Host ""
if (-not (Test-Path "models")) { New-Item -ItemType Directory -Path "models" | Out-Null }

if (Test-Path "models\kb_whisper_ggml_medium.bin") {
    Ok "Medium model already downloaded"
} else {
    Info "Downloading KB-LAB Swedish medium model (~1.5 GB)..."
    curl.exe -L --progress-bar -o "models\kb_whisper_ggml_medium.bin" `
        "https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin"
    Ok "Medium model downloaded"
}

if (Test-Path "models\kb_whisper_ggml_small.bin") {
    Ok "Small model already downloaded"
} else {
    Info "Downloading KB-LAB Swedish small model (~500 MB)..."
    curl.exe -L --progress-bar -o "models\kb_whisper_ggml_small.bin" `
        "https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin"
    Ok "Small model downloaded"
}

# -------------------------------------------
# Step 4: Start Docker services
# -------------------------------------------
Write-Host ""
$dockerRunning = docker compose ps --status running 2>$null | Select-String "postgres"
if ($dockerRunning) {
    Ok "Docker services already running"
} else {
    Info "Starting PostgreSQL and Redis..."
    docker compose up -d
    Ok "Docker services started"
}

# -------------------------------------------
# Step 5: Python virtual environment
# -------------------------------------------
Write-Host ""
if (Test-Path "venv") {
    Ok "Python venv already exists"
} else {
    Info "Creating Python virtual environment..."
    python -m venv venv
    Ok "Created venv"
}

Info "Installing Python dependencies (this may take a while)..."
& "venv\Scripts\activate.ps1"
pip install --upgrade pip -q
pip install -r requirements.txt -q
Ok "Python dependencies installed"

# -------------------------------------------
# Step 6: Frontend
# -------------------------------------------
Write-Host ""
if (Test-Path "frontend\node_modules") {
    Ok "Frontend dependencies already installed"
} else {
    Info "Installing frontend dependencies..."
    Push-Location frontend
    npm install --silent
    Pop-Location
    Ok "Frontend dependencies installed"
}

# -------------------------------------------
# Step 7: Create .env file
# -------------------------------------------
Write-Host ""
if (Test-Path ".env") {
    Ok ".env file already exists (not overwriting)"
} else {
    Info "Creating .env file..."
    $whisperCliPath = $whisperBin -replace '\\', '/'
    @"
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

WHISPER_CLI_PATH=$whisperCliPath
WHISPER_MODEL_PATH=./models/kb_whisper_ggml_medium.bin
WHISPER_SMALL_MODEL_PATH=./models/kb_whisper_ggml_small.bin

STORAGE_PATH=./storage

# Hugging Face token (needed for pyannote.audio speaker diarization)
# Get yours at https://huggingface.co/settings/tokens
# You must accept the model terms at https://huggingface.co/pyannote/speaker-diarization-3.1
HF_AUTH_TOKEN=hf_your_token_here
"@ | Set-Content -Path ".env" -Encoding UTF8
    Ok ".env file created"
    Warn "Edit .env and add your Hugging Face token before running!"
}

# -------------------------------------------
# Step 8: Check for Ollama
# -------------------------------------------
Write-Host ""
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Ok "Ollama is installed"
    $ollamaList = ollama list 2>$null
    if ($ollamaList -match "qwen3:8b") {
        Ok "qwen3:8b model is available"
    } else {
        Info "Pulling qwen3:8b model..."
        ollama pull qwen3:8b
    }
} else {
    Warn "Ollama not installed. Install from https://ollama.com or use OpenRouter instead."
}

# -------------------------------------------
# Done
# -------------------------------------------
Write-Host ""
Write-Host "========================================"
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "  Before first run, make sure to:"
Write-Host "    1. Edit .env and set HF_AUTH_TOKEN"
Write-Host "    2. Accept pyannote model terms at:"
Write-Host "       https://huggingface.co/pyannote/speaker-diarization-3.1"
Write-Host ""
Write-Host "  To start the app, run:"
Write-Host "    .\start.ps1"
Write-Host ""
Write-Host "  Or start manually in 4 terminals:"
Write-Host "    venv\Scripts\activate; uvicorn main:app --port 8000 --reload"
Write-Host "    venv\Scripts\activate; celery -A tasks.celery_app worker --loglevel=info --pool=solo"
Write-Host "    cd frontend; npm run dev"
Write-Host "    ollama serve"
Write-Host ""
Write-Host "  Then open http://localhost:5174"
Write-Host ""
