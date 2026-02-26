# ============================================================
# Stage 1: Build whisper.cpp
# ============================================================
FROM debian:bookworm-slim AS whisper-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake g++ make ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git /whisper.cpp

WORKDIR /whisper.cpp
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=OFF \
    && cmake --build build --config Release -j "$(nproc)"

# ============================================================
# Stage 2: Build frontend
# ============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent

COPY frontend/ ./

RUN npm run build

# ============================================================
# Stage 3: Final image
# ============================================================
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (install before copying code for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy whisper.cpp static binary (no shared library dependencies)
COPY --from=whisper-builder /whisper.cpp/build/bin/whisper-cli /usr/local/bin/whisper-cli

# Copy built frontend from builder
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy application code
COPY main.py config.py database.py model_config.py preferences.py ws_manager.py ./
COPY api/ ./api/
COPY services/ ./services/
COPY tasks/ ./tasks/
COPY models/ ./models/
COPY model_presets/ ./model_presets/

# Create directories (whisper model binaries go in /data/whisper-models)
RUN mkdir -p /app/storage /data/whisper-models /app/logs

# Config files from docker/ folder
COPY docker/nginx.conf /etc/nginx/sites-available/default
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh
# Fix Windows CRLF line endings and set executable
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Volumes for persistent data
VOLUME ["/app/storage", "/data/whisper-models"]

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
