#!/bin/bash
cd "$(dirname "$0")"
echo "Stopping Transcriber..."
docker compose down
echo ""
echo "Transcriber stopped."
