# AI Job Agent India

[![CI](https://github.com/vivans720/AI-Job-Search/actions/workflows/ci.yml/badge.svg)](https://github.com/vivans720/AI-Job-Search/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15.1-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent job discovery and recommendation engine tailored for the Indian tech job market, focusing on early-career engineers and freshers (0–2 years of experience). The system pairs deterministic 24-hour freshness gates and non-destructive skill-first scoring with resilient web crawling, local vector embeddings, multi-provider LLM intelligence, and Model Context Protocol (MCP) integration for autonomous agents.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Sources["Job Sources & Scrapers"]
        IN["Internshala Adapter (Playwright + HTTP)"]
        NK["Naukri Adapter (__NEXT_DATA__ + DOM)"]
        LI["LinkedIn Adapter (Guest API + Crawl4AI)"]
        C4["Crawl4AI Provider"] -.->|Render Fallback| LI
        TOR["Tor SOCKS5 Proxy"] -.->|Fallback on 403/429| HTTP["HTTP / Scraping Layer"]
        HTTP --> IN
        HTTP --> NK
        HTTP --> LI
    end

    subgraph Pipeline["Ingestion & Processing"]
        IN --> RAW["Raw Job Records"]
        NK --> RAW
        LI --> RAW
        RAW --> DEDUP["Deduplication & Hash Check"]
        DEDUP --> FRESH["24h Freshness Filter (IST)"]
        FRESH --> SKILLS["Skill Extraction (Regex + LLM)"]
        SKILLS --> EMBED["Local Vector Embeddings (FastEmbed 384d)"]
    end

    subgraph Storage["Storage & Queue"]
        EMBED --> PG[("PostgreSQL 16 + pgvector")]
        REDIS[("Redis 7 (Task Queue & Cache)")] <--> WORKER["Background Worker"]
        WORKER --> Pipeline
    end

    subgraph Matching["Matching Engine"]
        PG --> MATCH["6-Dimension Deterministic Scorer"]
        PROFILE["Candidate Profile & Preferences"] --> MATCH
    end

    subgraph Interfaces["Delivery Interfaces"]
        MATCH --> API["FastAPI Backend REST API"]
        API <--> WEB["Next.js 15.1 Web Dashboard"]
        API <--> MCP["FastMCP Server (stdio / SSE)"]
        MCP <--> AGENT["AI Agents (Hermes / Claude)"]
    end
```

---

## Key Implemented Features

### 1. Deterministic 24-Hour Freshness Enforcement
- **Backend Enforced**: Freshness is calculated in code against `Asia/Kolkata` (IST), never delegated to LLM prompt hallucination.
- **Configurable Horizon**: Discrete time filters (`1h`, `4h`, `8h`, `12h`, `16h`, `24h`) reject stale postings.
- **Relative Timestamp Parsing**: Accurately normalizes dynamic relative dates ("10 hours ago", "Active today", "Just now") into UTC timelines.

### 2. Skill-First Deterministic Matching Model
Scoring prioritizes proven technical capability over inflated job titles or uncalibrated semantic similarity:
- **Required Skills (65%)**: Direct matching against core technical requirements.
- **Preferred Skills (10%)**: Credit for bonus proficiencies.
- **Transferable Skills (10%)**: Partial credit via domain skill mappings.
- **Experience Alignment (5%)**: Evaluates early-career suitability (0–2 years).
- **Location Alignment (5%)**: Checks preferred cities or remote availability.
- **Preference Alignment (5%)**: Compares salary expectations and candidate preferences.
- **Recall-First Principle**: Jobs are not dropped due to low AI scores; lower-matching jobs are preserved and scored transparently so the candidate retains final judgment.

### 3. Production Scraping & Anti-Bot Camouflage
- **Internshala Adapter**: Isolated Chromium contexts with randomized viewports, stealth script injection (`navigator.webdriver` removal, realistic plugins), cookie clearing, and resilient HTTP fallbacks.
- **Naukri Adapter**: Extracts raw JSON payloads directly from embedded `__NEXT_DATA__` script tags, bypassing fragile DOM selector drift.
- **LinkedIn Adapter**: Fast unauthenticated public guest API querying recent postings (`f_TPR=r86400`), falling back to Crawl4AI rendered extraction or stealth Playwright.
- **Crawl4AI Provider**: Concurrency-bounded crawler abstraction (`Crawl4AICrawlerProvider`) powered by `crawl4ai` with JSON-CSS extraction.
- **Network Resilience**: Automatic failover to local Tor SOCKS5 proxy (`socks5://127.0.0.1:9050`) on HTTP 403 or 429 responses when Tor proxy is running.
- **Resource Rejection**: Playwright route filtering aborts heavy media (`.png`, `.jpg`, `.woff2`, `.mp4`) and analytics beacons, cutting load times and memory footprint.

### 4. Zero-Cloud Embedding & Multi-Provider AI Architecture
- **Local Dense Embeddings**: Generates 384-dimensional dense vector embeddings using `BAAI/bge-small-en-v1.5` via FastEmbed/ONNX runtime. Zero external API cost.
- **11 Registered AI Providers**: Configurable LLM provider registry (`app.intelligence.registry`) supporting:
  - **Local**: Ollama (default: `qwen3.5:9b`), OpenCode.
  - **Cloud & Gateways**: OpenAI, Google Gemini, Anthropic Claude, Groq, OpenRouter, Cerebras, Mistral, NVIDIA NIM, and custom OpenAI-compatible endpoints (vLLM, LiteLLM, OmniRoute).
- **Fallback Resilience**: Primary provider failures gracefully fall back to configured secondary providers.

### 5. Asynchronous Task Worker & Queue
- **Redis Job Queue**: Long-running crawling, multi-source sync, and AI enrichment tasks run asynchronously via `app.worker`.
- **Granular Progress Reporting**: Real-time per-source ingestion statistics (`discovered`, `saved`, `updated`, `duplicates`, `rate_limit_wait_ms`).
- **Synchronous Fallback**: Ingestion endpoints automatically fall back to synchronous execution when Redis queue is unavailable or when `async_mode=false` is requested.

### 6. Model Context Protocol (MCP) Interface
- Standalone FastMCP server (`mcp-server/server.py`) exposing 10 agentic tools over `stdio` or `sse`:
  - `get_candidate_profile`: Retrieve skills, preferences, and experience.
  - `search_jobs`: Query verified fresh jobs bounded by <= 24h age.
  - `get_job`: Fetch full job details and original application URL.
  - `match_job` & `rank_jobs`: Compute match breakdown and rank candidate lists.
  - `save_job`, `ignore_job`, `update_application_status`: Manage pipeline state.
  - `get_saved_jobs` & `get_search_history`: Audit active progress and query logs.
- **Manual Application Integrity**: Updates application state (`DISCOVERED`, `SAVED`, `VIEWED`, `APPLIED`, `INTERVIEW`, `REJECTED`, `OFFER`); strictly prohibits automated unauthorized applications.

### 7. Modern Next.js 15 Dashboard
- Built with Next.js 15.1 (App Router), React 19, TypeScript, and Tailwind CSS.
- **Discovery Radar (`/jobs`)**: Filterable feed with discrete freshness pills, role selectors, location tags, and real-time match breakdown modals.
- **Pipeline Tracker (`/saved`)**: Status-driven board managing application lifecycle stages.
- **Profile & Resume (`/profile`, `/resume`)**: PDF resume parser and skill profile editor.
- **Preferences (`/preferences`)**: Fine-grained configuration for target roles, excluded companies, and scoring thresholds.
- **AI Diagnostics (`/ai-provider`)**: Real-time provider switcher, latency ping tests, and capability inspection.

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Backend Framework** | Python 3.11+, FastAPI 0.115, Pydantic v2, Structlog |
| **Database & Vector** | PostgreSQL 16, pgvector, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic |
| **Caching & Queuing** | Redis 7, redis-py (asyncio), custom task worker |
| **Web Crawling** | Playwright (stealth), Crawl4AI 0.9+, BeautifulSoup4, HTTPX |
| **Embeddings & AI** | FastEmbed (`BAAI/bge-small-en-v1.5`), Ollama, OpenAI, Gemini, Anthropic |
| **Frontend** | Next.js 15.1, React 19, TypeScript 5, Tailwind CSS 3.4, Lucide React |
| **Agent Interface** | Model Context Protocol (FastMCP 1.x) |
| **Containerization** | Docker, Docker Compose |

---

## Repository Structure

```
.
├── backend/
│   ├── alembic/                # Database migration revisions
│   ├── app/
│   │   ├── api/v1/             # REST endpoints (jobs, profile, preferences, ai, sources)
│   │   ├── core/               # Logging, Redis pool, rate limiting, metrics
│   │   ├── crawling/           # Crawl4AI provider and browser abstractions
│   │   ├── intelligence/       # LLM provider registry, extractors, embeddings
│   │   ├── models/             # SQLAlchemy ORM models (Job, Company, Profile, etc.)
│   │   ├── schemas/            # Pydantic request and response schemas
│   │   ├── services/           # Matching, ingestion, dedup, freshness services
│   │   ├── sources/adapters/   # Scraper implementations (Internshala, Naukri, LinkedIn)
│   │   ├── utils/              # Browser stealth, Tor client, JSON-LD parser
│   │   ├── config.py           # Application configuration via Pydantic BaseSettings
│   │   ├── main.py             # FastAPI factory and middleware setup
│   │   └── worker.py           # Async Redis queue worker
│   ├── tests/                  # Backend test suite
│   ├── Dockerfile              # Production backend container definition
│   └── requirements.txt        # Backend dependencies
├── frontend/
│   ├── src/app/                # Next.js App Router pages (jobs, saved, profile, ai-provider)
│   ├── public/                 # Static assets
│   ├── Dockerfile              # Frontend container definition
│   └── package.json            # Node dependencies
├── mcp-server/
│   ├── server.py               # FastMCP server entry point
│   └── tools/                  # Handlers for candidate, job, search, and match tools
├── scripts/                    # Ingestion, seeding, and agent execution scripts
├── docker-compose.yml          # Multi-service stack (postgres, redis, backend, worker, frontend, ollama)
├── Makefile                    # Standard project task runner
└── .github/workflows/ci.yml    # Continuous integration pipeline
```

---

## Environment Variables

All settings are managed in `backend/app/config.py` and read from `.env` in the repository root:

### Core Infrastructure
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://jobagent:password@localhost:5432/jobagent` | Async PostgreSQL connection string |
| `POSTGRES_USER` | `jobagent` | Database username |
| `POSTGRES_PASSWORD` | `password` | Database password |
| `POSTGRES_DB` | `jobagent` | Database name |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

### Ingestion & Matching Gates
| Variable | Default | Description |
|---|---|---|
| `FRESHNESS_HOURS` | `24` | Maximum allowable posting age in hours |
| `DEFAULT_TIMEZONE` | `Asia/Kolkata` | Timezone for freshness evaluation |
| `EXPERIENCE_MAX_YEARS`| `2` | Maximum years of experience ceiling |
| `WEIGHT_REQUIRED_SKILL_MATCH` | `0.65` | Scoring weight for mandatory skills |
| `WEIGHT_PREFERRED_SKILL_MATCH` | `0.10` | Scoring weight for bonus skills |
| `WEIGHT_TRANSFERABLE_SKILL_MATCH` | `0.10` | Scoring weight for transferable skills |
| `WEIGHT_EXPERIENCE_MATCH` | `0.05` | Scoring weight for experience alignment |
| `WEIGHT_LOCATION_MATCH` | `0.05` | Scoring weight for location preference |
| `WEIGHT_PREFERENCE_MATCH` | `0.05` | Scoring weight for candidate preferences |

### Embeddings & AI Providers
| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` | Vector embedding backend (`local`) |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed ONNX model name |
| `EMBEDDING_DIMENSIONS`| `384` | Embedding vector dimensionality |
| `LLM_PROVIDER` | `ollama` | Active provider (`ollama`, `openai`, `gemini`, `anthropic`, `groq`, etc.) |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen3.5:9b` | Default Ollama model |
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `GEMINI_API_KEY` | `""` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | `""` | Anthropic Claude API key |
| `GROQ_API_KEY` | `""` | Groq API key |
| `OPENROUTER_API_KEY` | `""` | OpenRouter API key |
| `LLM_FALLBACK_PROVIDER` | `None` | Secondary provider ID for automated failover |

### Crawling & Scraper Hardening
| Variable | Default | Description |
|---|---|---|
| `SOURCE_INTERNSHALA_ENABLED` | `true` | Enable/disable Internshala adapter |
| `SOURCE_NAUKRI_ENABLED` | `true` | Enable/disable Naukri adapter |
| `SOURCE_LINKEDIN_ENABLED` | `true` | Enable/disable LinkedIn adapter |
| `CRAWL4AI_ENABLED` | `true` | Enable Crawl4AI provider fallback |
| `CRAWL4AI_HEADLESS` | `true` | Run Crawl4AI browser in headless mode |
| `CRAWL4AI_MAX_CONCURRENCY` | `3` | Maximum concurrent page crawls |
| `BROWSER_USER_DATA_DIR` | `~/.config/job_agent_browser_profile` | Path to persistent browser profile |
| `TOR_ENABLED` | `true` | Enable fallback through Tor SOCKS5 proxy |
| `TOR_PROXY_URL` | `socks5://127.0.0.1:9050` | Local Tor SOCKS5 proxy address |

---

## Getting Started

### Option A: Complete Docker Compose Stack

Start all services (PostgreSQL with pgvector, Redis, FastAPI backend, background worker, Next.js frontend, and Ollama) with Docker Compose:

```bash
docker compose up --build -d
# or: make docker-up
```

Verify services are healthy:
```bash
docker compose ps
```

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

Stop services:
```bash
docker compose down
# or: make docker-down
```

---

### Option B: Local Development Setup

#### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for PostgreSQL and Redis)

#### 2. Start Supporting Services
Start PostgreSQL (with pgvector) and Redis:
```bash
make db-up
# or: docker compose up -d postgres redis
```

#### 3. Setup and Run Backend
Configure environment:
```bash
cp .env.example .env
```

Install Python dependencies and Playwright browser:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
playwright install chromium
cd ..
```

Start the FastAPI backend server:
```bash
make backend
# or: ./backend.sh
```

Verify backend connectivity:
```bash
curl http://localhost:8000/api/health
# Response: {"status":"ok","database":"connected","pgvector":true}
```

Seed initial candidate profile and resume:
```bash
make seed
# or: backend/.venv/bin/python scripts/seed_candidate_resume.py
```

#### 4. Start Background Worker (Optional for Async Sync)
```bash
make worker
# or: cd backend && .venv/bin/python -m app.worker
```

#### 5. Setup and Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Live Ingestion & Sync Commands

Trigger live ingestion across supported job boards directly from CLI or API:

```bash
# Sync Internshala opportunities
backend/.venv/bin/python scripts/sync_internshala.py

# Sync Naukri opportunities
backend/.venv/bin/python scripts/sync_naukri.py

# Sync LinkedIn opportunities
backend/.venv/bin/python scripts/sync_linkedin.py

# Trigger sync via REST API (asynchronous queue execution)
curl -X POST "http://localhost:8000/api/v1/jobs/sync?source=all"

# Trigger synchronous sync via REST API
curl -X POST "http://localhost:8000/api/v1/jobs/sync?source=all&async_mode=false"
```

---

## Model Context Protocol (MCP) Setup

Run the standalone FastMCP server:
```bash
make mcp
# or: backend/.venv/bin/python mcp-server/server.py
```

Register with an MCP-compatible client (e.g. Hermes Agent, Claude Desktop):

```json
{
  "mcpServers": {
    "job-agent-india": {
      "command": "/path/to/backend/.venv/bin/python",
      "args": ["/path/to/mcp-server/server.py"]
    }
  }
}
```

---

## Testing & Verification

The codebase includes an automated test suite covering database operations, normalization logic, deduplication, freshness enforcement, matching algorithms, and fault recovery.

Run backend test suite:
```bash
backend/.venv/bin/python -m pytest backend/tests/ -v
```

Run frontend linting and production build:
```bash
cd frontend
npm run lint
npm run build
```

Run CI pipeline tasks locally:
```bash
make ci
```

---

## License

This project is licensed under the [MIT License](LICENSE).
