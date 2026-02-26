@echo off
title Transcriber
echo ========================================
echo   Transcriber - Starting...
echo ========================================
echo.
echo First run will download models (~7 GB). Please be patient.
echo.

docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Docker is not running.
    echo Please start Docker Desktop first, then try again.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Transcriber is running!
echo   Opening http://localhost:8080
echo ========================================
echo.
echo To stop: run stop.bat or use Docker Desktop
echo.

timeout /t 3 >nul
start http://localhost:8080

pause
