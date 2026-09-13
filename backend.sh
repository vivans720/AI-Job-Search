#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"
echo "🔄 Running database migrations..."
.venv/bin/alembic upgrade head

echo "🚀 Starting Job Search AI worker..."
.venv/bin/python3 -m app.worker &
WORKER_PID=$!

trap "echo '🛑 Stopping worker...'; kill -TERM $WORKER_PID 2>/dev/null || true; exit" SIGINT SIGTERM EXIT

echo "🚀 Starting Job Search AI backend on http://localhost:8000..."
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

