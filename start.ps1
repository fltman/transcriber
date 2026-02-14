# Transcriber start script for Windows
# Starts all services in separate windows.
# Usage: powershell -ExecutionPolicy Bypass -File start.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Starting Transcriber services..." -ForegroundColor Cyan
Write-Host ""

# Make sure Docker services are running
docker compose up -d 2>$null

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$PWD'; .\venv\Scripts\activate.ps1; uvicorn main:app --port 8000 --reload" `
    -WindowStyle Normal
Write-Host "[1/3] Backend started (port 8000)" -ForegroundColor Green

# Celery
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$PWD'; .\venv\Scripts\activate.ps1; celery -A tasks.celery_app worker --loglevel=info --pool=solo" `
    -WindowStyle Normal
Write-Host "[2/3] Celery worker started" -ForegroundColor Green

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$PWD\frontend'; npm run dev" `
    -WindowStyle Normal
Write-Host "[3/3] Frontend started (port 5174)" -ForegroundColor Green

Write-Host ""
Write-Host "All services running!" -ForegroundColor Green
Write-Host "  App: http://localhost:5174"
Write-Host ""
Write-Host "Each service runs in its own window. Close the windows to stop."
Write-Host ""

# Open browser after a short delay
Start-Sleep -Seconds 4
Start-Process "http://localhost:5174"
