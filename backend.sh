#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"
echo "🚀 Starting Job Search AI backend on http://localhost:8000..."
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
