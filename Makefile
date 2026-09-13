.PHONY: help setup db-up db-down db-logs backend frontend worker sync agent mcp test lint clean seed

help:
	@echo "Available commands:"
	@echo "  make setup        - Install Python & Node dependencies"
	@echo "  make docker-up    - Build and start full stack via docker compose"
	@echo "  make docker-down  - Stop full docker stack"
	@echo "  make docker-logs  - View full stack logs"
	@echo "  make db-up        - Start postgres container with pgvector"
	@echo "  make db-down      - Stop postgres container"
	@echo "  make db-logs      - View postgres container logs"
	@echo "  make backend      - Start FastAPI backend server"
	@echo "  make worker       - Start background job queue worker"
	@echo "  make frontend     - Start Next.js development server"
	@echo "  make seed         - Seed initial candidate profile into database"
	@echo "  make sync         - Run live job ingestion script"
	@echo "  make agent        - Execute candidate job matching agent"
	@echo "  make mcp          - Start standalone MCP server"
	@echo "  make test         - Run pytest test suite"
	@echo "  make lint         - Run ruff lint check on backend"
	@echo "  make clean        - Clean python caches and temporary build files"


setup:
	@cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium
	@cd frontend && npm install

docker-up:
	@docker compose up --build -d

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f

db-up:
	@docker compose up -d postgres


db-down:
	@docker compose down

db-logs:
	@docker compose logs -f postgres

backend:
	@./backend.sh

worker:
	@cd backend && .venv/bin/python3 -m app.worker

frontend:
	@cd frontend && npm run dev

seed:
	@backend/.venv/bin/python3 scripts/seed_candidate_resume.py

sync:
	@backend/.venv/bin/python3 scripts/sync_internshala.py

agent:
	@backend/.venv/bin/python3 scripts/run_job_agent.py

mcp:
	@backend/.venv/bin/python3 mcp-server/server.py

test:
	@backend/.venv/bin/python3 -m pytest backend/tests/ tests/test_freshness.py tests/test_dedup.py tests/test_normalization.py -v

lint:
	@if [ -x backend/.venv/bin/ruff ]; then backend/.venv/bin/ruff check backend/; else echo "ruff not installed in .venv; running flake8 or skipping"; fi

ci: lint test
	@cd frontend && npm run lint && npm run build

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@rm -rf frontend/.next
	@rm -f :memory:.ses
