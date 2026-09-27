# Single-service image for Render (and any Docker host): FastAPI serves the API
# and the built React app. LLM = Groq (GROQ_API_KEY), embeddings = fastembed on CPU.

# ---- 1. Build the frontend -------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Backend runtime ----------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    LLM_PROVIDER=groq \
    EMBEDDING_PROVIDER=fastembed \
    FASTEMBED_CACHE_DIR=/app/models \
    HF_HUB_DISABLE_TELEMETRY=1 \
    CHROMA_PERSIST_DIRECTORY=/app/data/chroma \
    SOURCES_CSV=/app/data/sources.csv \
    DOCUMENTS_DIR=/app/data/documents \
    SERVE_FRONTEND_DIR=/app/frontend-dist

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY scripts /app/scripts
COPY data/sources.csv /app/data/sources.csv
COPY data/chroma /app/data/chroma
COPY --from=frontend /app/frontend/dist /app/frontend-dist

# Bake the embedding model into the image (Render's filesystem is ephemeral).
RUN python -c "from app.rag.embeddings import warm_up; warm_up()"
# Use the prebuilt index from the repo; build it only if it is missing.
RUN test -f /app/data/chroma/chroma.sqlite3 || python /app/scripts/ingest_sources.py

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
