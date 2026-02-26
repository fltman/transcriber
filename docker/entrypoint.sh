#!/usr/bin/env bash
set -e

echo "========================================"
echo "  Transcriber - Docker Startup"
echo "========================================"

# -------------------------------------------
# Download Whisper models if not present
# -------------------------------------------
if [ ! -f "/data/whisper-models/kb_whisper_ggml_medium.bin" ]; then
    echo "[INFO] Downloading KB-LAB Swedish medium model (~1.5 GB)..."
    curl -L --progress-bar -o /data/whisper-models/kb_whisper_ggml_medium.bin \
        https://huggingface.co/KBLab/kb-whisper-medium/resolve/main/ggml-model.bin
    echo "[OK] Medium model downloaded"
else
    echo "[OK] Medium model already present"
fi

if [ ! -f "/data/whisper-models/kb_whisper_ggml_small.bin" ]; then
    echo "[INFO] Downloading KB-LAB Swedish small model (~500 MB)..."
    curl -L --progress-bar -o /data/whisper-models/kb_whisper_ggml_small.bin \
        https://huggingface.co/KBLab/kb-whisper-small/resolve/main/ggml-model.bin
    echo "[OK] Small model downloaded"
else
    echo "[OK] Small model already present"
fi

# -------------------------------------------
# Wait for PostgreSQL
# -------------------------------------------
echo "[INFO] Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if python3 -c "
import sqlalchemy
engine = sqlalchemy.create_engine('$DATABASE_URL')
with engine.connect() as c:
    c.execute(sqlalchemy.text('SELECT 1'))
" 2>/dev/null; then
        echo "[OK] PostgreSQL is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        echo "[WARN] PostgreSQL not ready after 30s, starting anyway..."
    fi
    sleep 1
done

# -------------------------------------------
# Wait for Redis
# -------------------------------------------
echo "[INFO] Waiting for Redis..."
for i in $(seq 1 30); do
    if python3 -c "
import redis
r = redis.Redis.from_url('$REDIS_URL')
r.ping()
" 2>/dev/null; then
        echo "[OK] Redis is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        echo "[WARN] Redis not ready after 30s, starting anyway..."
    fi
    sleep 1
done

# -------------------------------------------
# Pull Ollama model in background (don't block app startup)
# -------------------------------------------
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ] && [ -n "${OLLAMA_BASE_URL:-}" ]; then
    (
        echo "[INFO] Waiting for Ollama at ${OLLAMA_BASE_URL}..."
        OLLAMA_READY=0
        for i in $(seq 1 60); do
            if curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
                OLLAMA_READY=1
                echo "[OK] Ollama is reachable"
                break
            fi
            sleep 1
        done

        if [ "$OLLAMA_READY" = "1" ]; then
            MODEL_EXISTS=$(curl -sf "${OLLAMA_BASE_URL}/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
target = '${OLLAMA_MODEL:-qwen3:8b}'
print('yes' if any(target in m for m in models) else 'no')
" 2>/dev/null || echo "no")

            if [ "$MODEL_EXISTS" = "yes" ]; then
                echo "[OK] Model '${OLLAMA_MODEL:-qwen3:8b}' already available"
            else
                echo "[INFO] Pulling model '${OLLAMA_MODEL:-qwen3:8b}' (this may take a while)..."
                curl -sf "${OLLAMA_BASE_URL}/api/pull" \
                    -d "{\"name\": \"${OLLAMA_MODEL:-qwen3:8b}\", \"stream\": false}" \
                    --max-time 1800 >/dev/null 2>&1 \
                    && echo "[OK] Model '${OLLAMA_MODEL:-qwen3:8b}' pulled successfully" \
                    || echo "[WARN] Model pull may have failed - LLM features may not work"
            fi
        else
            echo "[WARN] Ollama not reachable after 60s, skipping model pull"
            echo "       LLM features (analysis, actions) will not work until Ollama is available"
        fi
    ) &
fi

echo ""
echo "[INFO] Starting services..."
echo "  App will be available at http://localhost:${PORT:-80}"
echo ""

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
