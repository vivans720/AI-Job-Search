#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"

cleanup() {
    echo ""
    echo "🛑 Shutting down backend services..."
    if [ -n "$WORKER_PID" ]; then
        echo "🛑 Stopping worker (PID: $WORKER_PID)..."
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi

    echo "🛑 Stopping supporting Docker containers..."
    (cd "$ROOT_DIR" && docker compose stop postgres redis 2>/dev/null || true)
    echo "✅ Backend shutdown and containers closed cleanly."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "🔄 Running database migrations..."
.venv/bin/alembic upgrade head

echo "🚀 Starting Job Search AI worker..."
.venv/bin/python3 -m app.worker &
WORKER_PID=$!

echo "🚀 Starting Job Search AI backend on http://localhost:8000..."
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
