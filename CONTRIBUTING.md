# Contributing to AI Job Agent India

Thank you for contributing to AI Job Agent India! This guide helps you set up the development environment and follow project standards.

---

## Core Architecture Principles

1. **Recall-First Architecture**: Ingestion pipeline must never discard fresh jobs due to subjective thresholds (experience > 2y, short description, low AI score). Backend persists valid raw jobs and extracts metadata deterministically.
2. **Manual Applications Only**: The system recommends jobs and supplies verified original apply links. Never automate application submission.
3. **Deterministic First, AI Second**: Technical skill matching and eligibility checks are deterministic rules. LLMs serve as fallback extractors and enrichment layers.
4. **Strict 24-Hour Freshness**: Evaluated strictly in `Asia/Kolkata` (IST) timestamp arithmetic.
5. **Decoupled Components**: The core system runs locally without requiring Hermes Agent or MCP to function.

---

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (tested on Node 20+)
- Docker and Docker Compose
- Running LLM runtime (Ollama or OmniRoute on port 20128)

### Local Step-by-Step

1. **Clone repository**:
   ```bash
   git clone https://github.com/vivans720/AI-Job-Search.git
   cd AI-Job-Search
   ```

2. **Start Database**:
   ```bash
   make db-up
   # or docker compose up -d postgres
   ```

3. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```

4. **Python Virtualenv & Dependencies**:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   cd ..
   ```

5. **Frontend Dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

6. **Seed Initial Resume & Test**:
   ```bash
   make seed
   make test
   ```

---

## Makefile Commands

| Command | Action |
|---|---|
| `make db-up` | Start Postgres container with pgvector |
| `make db-down` | Stop Postgres container |
| `make backend` | Launch FastAPI backend with reload (`http://localhost:8000`) |
| `make frontend` | Launch Next.js dashboard (`http://localhost:3000`) |
| `make sync` | Ingest live jobs from Internshala |
| `make agent` | Run deterministic matching agent loop |
| `make test` | Run test suite with pytest |
| `make lint` | Run code quality checks |
| `make clean` | Clean up Python and Next.js caches |

---

## Branching & Commit Conventions

- Use feature branches: `git checkout -b feat/your-feature-name` or `fix/issue-description`.
- Follow Conventional Commits:
  - `feat: ...` for new capabilities.
  - `fix: ...` for bug fixes.
  - `docs: ...` for documentation updates.
  - `refactor: ...` for code cleanup without functional alterations.
  - `test: ...` for new or modified test cases.

---

## Code Quality Standards

- Python formatting & linting: `ruff check backend/`
- Async I/O: Use `async`/`await` properly; database queries must use `AsyncSession`.
- Test additions: Place backend integration or unit tests in `tests/`.
- Ensure `make test` passes before opening pull requests.
