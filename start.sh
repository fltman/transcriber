#!/usr/bin/env bash
set -e

# Transcriber start script for macOS and Linux
# Starts all services in the background and tails logs.
# Usage: bash start.sh
# Stop:  bash start.sh stop

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

LOGDIR="./logs"
mkdir -p "$LOGDIR"

stop_all() {
  echo -e "${BLUE}Stopping services...${NC}"
  [ -f "$LOGDIR/backend.pid" ]  && kill "$(cat "$LOGDIR/backend.pid")" 2>/dev/null && rm "$LOGDIR/backend.pid"
  [ -f "$LOGDIR/celery.pid" ]   && kill "$(cat "$LOGDIR/celery.pid")" 2>/dev/null && rm "$LOGDIR/celery.pid"
  [ -f "$LOGDIR/frontend.pid" ] && kill "$(cat "$LOGDIR/frontend.pid")" 2>/dev/null && rm "$LOGDIR/frontend.pid"
  echo -e "${GREEN}All services stopped.${NC}"
}

if [ "${1:-}" = "stop" ]; then
  stop_all
  exit 0
fi

# Make sure Docker services are running
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null

# Activate venv
source venv/bin/activate

echo -e "${BLUE}Starting services...${NC}"

# Backend
uvicorn main:app --port 8000 --reload > "$LOGDIR/backend.log" 2>&1 &
echo $! > "$LOGDIR/backend.pid"
echo -e "${GREEN}[1/3]${NC} Backend started (port 8000)"

# Celery
celery -A tasks.celery_app worker --loglevel=info --pool=solo > "$LOGDIR/celery.log" 2>&1 &
echo $! > "$LOGDIR/celery.pid"
echo -e "${GREEN}[2/3]${NC} Celery worker started"

# Frontend
cd frontend
npm run dev > "../$LOGDIR/frontend.log" 2>&1 &
echo $! > "../$LOGDIR/frontend.pid"
cd ..
echo -e "${GREEN}[3/3]${NC} Frontend started (port 5174)"

echo ""
echo -e "${GREEN}All services running!${NC}"
echo "  App:  http://localhost:5174"
echo "  Logs: $LOGDIR/"
echo "  Stop: bash start.sh stop"
echo ""
echo "Tailing logs (Ctrl+C to detach, services keep running)..."
echo ""
tail -f "$LOGDIR/backend.log" "$LOGDIR/celery.log" "$LOGDIR/frontend.log"
