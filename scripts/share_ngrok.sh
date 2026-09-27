#!/usr/bin/env bash
# Share the app publicly through a single ngrok tunnel.
#   Prerequisites: Ollama running, index built, `ngrok config add-authtoken <token>` done once.
#   Usage: ./scripts/share_ngrok.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT=4173

cleanup() { kill "${BACKEND_PID:-}" "${PREVIEW_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT

if ! curl -s -m 2 http://127.0.0.1:8000/api/health >/dev/null; then
  echo "Starting backend on :8000 ..."
  (cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
  BACKEND_PID=$!
fi

echo "Building frontend ..."
(cd "$ROOT/frontend" && npm run build >/dev/null)

echo "Starting production preview on :$PORT (proxies /api to :8000) ..."
(cd "$ROOT/frontend" && npx vite preview --host 127.0.0.1 --port $PORT --strictPort) &
PREVIEW_PID=$!
sleep 2

echo "Opening ngrok tunnel - share the https://... Forwarding URL it prints."
ngrok http $PORT
