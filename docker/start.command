#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  Transcriber - Starting..."
echo "========================================"
echo ""
echo "First run will download models (~7 GB). Please be patient."
echo ""

if ! docker compose up -d; then
    echo ""
    echo "ERROR: Docker is not running."
    echo "Please start Docker Desktop first, then try again."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

echo ""
echo "========================================"
echo "  Transcriber is running!"
echo "  Opening http://localhost:8080"
echo "========================================"
echo ""
echo "To stop: run stop.command or use Docker Desktop"
echo ""

sleep 3
open http://localhost:8080
