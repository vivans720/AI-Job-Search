# AI Job Agent India

[![CI](https://github.com/vivans720/AI-Job-Search/actions/workflows/ci.yml/badge.svg)](https://github.com/vivans720/AI-Job-Search/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15.1-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent job discovery and recommendation engine tailored for the Indian tech job market, focusing on early-career engineers and freshers (0–2 years of experience). The system pairs deterministic 24-hour freshness gates and non-destructive skill-first scoring with resilient web crawling, local vector embeddings, multi-provider LLM intelligence, and a fully autonomous Model Context Protocol (MCP) agent interface capable of researching job pages, preparing applications, and delivering daily job digests.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Sources["Job Sources & Scrapers"]
        IN["Internshala Adapter (Playwright + HTTP)"]
        NK["Naukri Adapter (__NEXT_DATA__ + DOM)"]
        LI["LinkedIn Adapter (Guest API + Crawl4AI)"]
        C4["Crawl4AI Provider"] -.-|Render Fallback| LI
        TOR["Tor SOCKS5 Proxy"] -.-|Fallback on 403/429| HTTP["HTTP / Scraping Layer"]
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
        FRESH --> SKILLS["Skill Extraction (Deterministic Taxonomy + Regex)"]
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
        API <--> MCP["FastMCP Server (stdio / SSE) — 33 tools"]
        MCP <--> AGENT["Hermes / Claude (Autonomous Agent)"]
        AGENT -->|"Daily Digest Cron (0 9 * * *)"| MCP
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
- **Recall-First Principle**: Jobs are never dropped due to low AI scores; lower-matching jobs are preserved and scored transparently so the candidate retains final judgment.

### 3. Production Scraping & Anti-Bot Camouflage
- **Internshala Adapter**: Isolated Chromium contexts with randomized viewports, stealth script injection (`navigator.webdriver` removal, realistic plugins), cookie clearing, and resilient HTTP fallbacks.
- **Naukri Adapter**: Extracts raw JSON payloads directly from embedded `__NEXT_DATA__` script tags, bypassing fragile DOM selector drift.
- **LinkedIn Adapter**: Fast unauthenticated public guest API querying recent postings (`f_TPR=r86400`), falling back to Crawl4AI rendered extraction or stealth Playwright.
- **Crawl4AI Provider**: Concurrency-bounded crawler abstraction (`Crawl4AICrawlerProvider`) powered by `crawl4ai` with JSON-CSS extraction.
- **Network Resilience**: Automatic failover to local Tor SOCKS5 proxy (`socks5://127.0.0.1:9050`) on HTTP 403 or 429 responses when Tor proxy is running.
- **Resource Rejection**: Playwright route filtering aborts heavy media (`.png`, `.jpg`, `.woff2`, `.mp4`) and analytics beacons, cutting load times and memory footprint.

### 4. Zero-Cloud Embedding & Multi-Provider AI Architecture
- **Local Dense Embeddings**: Generates 384-dimensional dense vector embeddings using `BAAI/bge-small-en-v1.5` via FastEmbed/ONNX runtime. Zero external API cost.
- **Semantic Vector Search**: `semantic_search_jobs` tool performs pgvector cosine-distance search over fresh jobs for concept-level retrieval beyond keyword matching.
- **OmniRoute Single AI Gateway**: All LLM inference routes through a unified OpenAI-compatible gateway (`app.intelligence.registry` → `OpenAICompatibleProvider`). Any OpenAI-compatible backend — including self-hosted vLLM, LiteLLM, or Ollama behind OmniRoute — is supported transparently via `OMNIROUTE_BASE_URL` and `OMNIROUTE_MODEL`.

### 5. Asynchronous Task Worker & Queue
- **Redis Job Queue**: Long-running crawling, multi-source sync, and AI enrichment tasks run asynchronously via `app.worker`.
- **Granular Progress Reporting**: Real-time per-source ingestion statistics (`discovered`, `saved`, `updated`, `duplicates`, `rate_limit_wait_ms`).
- **Synchronous Fallback**: Ingestion endpoints automatically fall back to synchronous execution when Redis queue is unavailable or when `async_mode=false` is requested.

### 6. Model Context Protocol (MCP) Interface — 33 Tools
Standalone FastMCP server (`mcp-server/server.py`) exposing 33 agentic tools over `stdio` or `sse` across 8 modules:

**Profile & Preferences**
- `get_candidate_profile` — Retrieve structured candidate intelligence from parsed resume.
- `get_preferences` — Fetch search/sync preferences (freshness, locations, roles, source boards).
- `update_preferences` — Safely update search and filtering preferences with validation.

**Job Search & Ingestion**
- `search_jobs` — Keyword/filter search bounded to freshness window (≤24h).
- `semantic_search_jobs` — pgvector cosine-distance search for concept-level retrieval.
- `get_job` / `get_jobs` — Fetch full details and match scores for one or many jobs.
- `sync_jobs` — Trigger live aggregation from LinkedIn, Naukri, Internshala.
- `get_search_history` — Audit recent search queries and freshness statistics.

**Matching & Ranking**
- `match_job` — 6-dimension match breakdown for a specific job against candidate profile.
- `rank_jobs` — Rank a list of job IDs by relevance and match score.

**Pipeline & Curation**
- `save_job` / `batch_save_jobs` — Save or batch-recommend jobs (subject to approval policy).
- `dismiss_job` / `ignore_job` — Remove jobs from recommendations.
- `get_pipeline` / `get_saved_jobs` — List tracked jobs, optionally filtered by stage.
- `get_application` / `update_application` / `update_application_status` / `update_pipeline_status` — Manage application lifecycle.
- `check_approval_status` — Poll queued approval requests (save, dismiss, apply actions).

**Deep Browser Research (Phase 8)**
- `research_job_page` — Live Playwright inspection of job posting URL: extracts requirements, team context, application questions, and hiring status.
- `get_job_research` — Retrieve previously recorded browser research insights for a job.

**Application Preparation (Phase 9)**
- `prepare_application` — Prepare complete application package (resume selection, cover letter, Q&A) without submitting. Places job in `READY_FOR_REVIEW` state.
- `prepare_resume` — `EXISTING` preserves active resume; `TAILORED` reframes experience with strict anti-hallucination grounding.
- `generate_cover_letter` — Authentic tailored cover letter based on candidate profile and browser research.
- `generate_application_answers` — Grounded answers to screening questions, flagging missing information.
- `get_application_preparation` — Retrieve current prep status, resume, cover letter, and answers.

**Daily Digest & Scheduled Search (Phase 10)**
- `run_scheduled_job_search` — Autonomous morning search: discovers fresh jobs, deduplicates previously alerted ones, scores fit, and creates daily briefing.
- `create_daily_digest` — Save a formatted morning digest into the candidate feed, tracking notified job IDs to prevent duplicate alerts.
- `get_daily_digests` — Retrieve recent daily digests and briefings.

**Activity Stream**
- `notify_activity` — Broadcast human-readable agent milestone messages to the activity stream (e.g. "Filtered 45 jobs down to 8 matches"). Never exposes raw chain-of-thought.

**Manual Application Integrity**: Pipeline state machine (`DISCOVERED` → `SAVED` → `VIEWED` → `PREPARING` → `READY_TO_APPLY` → `APPLIED` → `INTERVIEW` → `REJECTED` / `OFFER` / `IGNORED`) strictly prohibits automated unauthorized submissions. Transitions to `APPLIED` require explicit user confirmation.

**Autonomy Approval Gate**: Agent actions that mutate pipeline state (save, dismiss, batch operations) are intercepted by an approval policy. When active, the agent queues an approval request; the candidate reviews and confirms in the UI before the mutation is committed.

### 7. Autonomous Daily Digest (Scheduled Morning Search)
- **Hermes Cron**: `scripts/hermes_cron_setup.py` registers a `0 9 * * *` Hermes scheduled task that runs the full morning job hunt autonomously.
- **Duplicate Prevention**: `DigestNotifiedJob` table tracks job IDs included in previous digests; subsequent runs exclude already-alerted jobs.
- **Zero-Match Handling**: Digest generated even when no matching jobs found, with actionable guidance.
- **Agent Activity Logging**: Each scheduled run records `AgentRun` records and milestone events for full observability.

### 8. Company Logo Enrichment & Ingestion Pipeline
- **Adapter Ingestion**: Scrapers extract verified company logos directly from LinkedIn (`img.artdeco-entity-image`), Internshala (`.company_logo img`), and Naukri (`logoPath` in `__NEXT_DATA__` JSON or `.comp-logo img`).
- **Database & Schemas**: Dedicated `company_logo_url` and `logo_url` columns on jobs and companies tables with database migrations.
- **Resilient Fallback**: Discovery feed and detail drawers render company logos with clean fallback to company initials monogram when image assets are missing or fail to load.

### 9. Company Autosuggest & Multi-Add Preferences
- **Autosuggest Endpoint**: `GET /api/v1/companies/suggest?q=...&limit=8` delivers real-time case-insensitive prefix search against ingested employer entities.
- **Interactive Multi-Entry**: Fast pill suggestions, interactive tags, and comma/newline batch pasting for excluded companies, priority companies, and locations.

### 10. Modern Next.js 15 Dashboard & Design System
- Built with Next.js 15.1 (App Router), React 19, TypeScript, and Tailwind CSS.
- **Design System Primitives**: Standardized atomic UI components in `@/components/ui` (`Button`, `Badge`, `Card`, `Input`, `Tabs`, `PageHeader`) using a unified Light SaaS palette (`#f8f9fc` canvas, `#ffffff` cards, `#059669` emerald telemetry, hairline borders).
- **Discovery Radar (`/jobs`)**: Filterable feed with discrete freshness pills, role selectors, location tags, telemetry distribution bar, keyboard navigation (`J`/`K`/`Enter`/`S`/`X`), and real-time match breakdown modals.
- **Pipeline Tracker (`/saved`)**: Status-driven board managing full 10-stage application lifecycle with tabular counters.
- **Profile & Resume (`/profile`)**: Consolidated resume intelligence center featuring PDF resume parser, SHA256 verification, extracted skill overview, and candidate profile editor (`/resume` redirects cleanly).
- **Preferences (`/preferences`)**: Fine-grained configuration for target roles, autosuggested priority/excluded companies, and scoring thresholds.
- **Settings (`/settings`)**: Application-level settings and agent autonomy policy controls.
- **AI Diagnostics (`/ai-provider`)**: Real-time provider switcher, latency ping tests, and capability inspection.

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Backend Framework** | Python 3.11+, FastAPI 0.115, Pydantic v2, Structlog |
| **Database & Vector** | PostgreSQL 16, pgvector, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic |
| **Caching & Queuing** | Redis 7, redis-py (asyncio), custom task worker |
| **Web Crawling** | Playwright (stealth), Crawl4AI 0.9+, BeautifulSoup4, HTTPX |
| **Embeddings & AI** | FastEmbed (`BAAI/bge-small-en-v1.5`), OmniRoute AI Gateway (OpenAI-compatible) |
| **Frontend** | Next.js 15.1, React 19, TypeScript 5, Tailwind CSS 3.4, Lucide React |
| **Agent Interface** | Model Context Protocol (FastMCP 1.x) — 33 tools |
| **Containerization** | Docker, Docker Compose |

---

## Repository Structure

```
.
├── backend/
│   ├── alembic/                # Database migration revisions
│   ├── app/
│   │   ├── api/v1/             # REST endpoints (jobs, profile, preferences, ai, sources, dashboard, companies, agent_activity, application_prep, digests)
│   │   ├── core/               # Logging, Redis pool, rate limiting, metrics
│   │   ├── crawling/           # Crawl4AI provider and browser abstractions
│   │   ├── intelligence/       # LLM provider registry, extractors, embeddings
│   │   ├── models/             # SQLAlchemy ORM models (Job, Company, Profile, AgentRun, DailyDigest, etc.)
│   │   ├── schemas/            # Pydantic request and response schemas
│   │   ├── services/           # Matching, ingestion, dedup, freshness, scheduled search, application prep services
│   │   ├── sources/adapters/   # Scraper implementations (Internshala, Naukri, LinkedIn)
│   │   ├── utils/              # Browser stealth, Tor client, JSON-LD parser, HTTP client
│   │   ├── config.py           # Application configuration via Pydantic BaseSettings
│   │   ├── main.py             # FastAPI factory and middleware setup
│   │   └── worker.py           # Async Redis queue worker
│   ├── tests/                  # Backend test suite
│   ├── Dockerfile              # Production backend container definition
│   └── requirements.txt        # Backend dependencies
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages (jobs, saved, profile, preferences, settings, ai-provider)
│   │   ├── components/
│   │   │   ├── ui/             # Reusable design system primitives (Button, Badge, Card, Input, Tabs, PageHeader)
│   │   │   ├── jobs/           # Discovery radar components, drawers, ApplicationHandoffModal
│   │   │   └── agent/          # DailyDigestBanner and agent activity components
│   │   └── lib/                # API clients, types, and company autosuggest helpers
│   ├── public/                 # Static assets
│   ├── Dockerfile              # Frontend container definition
│   └── package.json            # Node dependencies
├── mcp-server/
│   ├── server.py               # FastMCP server entry point (33 tools)
│   ├── middleware/             # Activity logger middleware for all tool calls
│   └── tools/                  # Tool handlers: profile, search, job, match, activity, research, application, digest
├── scripts/                    # Ingestion, seeding, agent execution, and Hermes cron setup scripts
├── docker-compose.yml          # Multi-service stack (postgres, redis, backend, worker, frontend, optional ollama)
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
| `LLM_PROVIDER` | `omniroute` | Inference gateway identifier |
| `OMNIROUTE_BASE_URL` | `http://localhost:8000/v1` | OmniRoute API endpoint |
| `OMNIROUTE_API_KEY` | `""` | OmniRoute API key (if required by your gateway) |
| `OMNIROUTE_MODEL` | `gpt-4o-mini` | Active model routed through OmniRoute |
| `OMNIROUTE_TIMEOUT` | `45.0` | Request timeout in seconds |
| `DEFAULT_AGENT_MODEL` | `gpt-4o-mini` | Default model for autonomous agent sessions |

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

Start services (PostgreSQL with pgvector, Redis, FastAPI backend, background worker, and Next.js frontend) with Docker Compose:

```bash
docker compose up --build -d
# or: make docker-up
```

> **Note**: Ollama is optional and not pulled by default. To start local Ollama along with the stack:
> ```bash
> docker compose --profile ollama up --build -d
> ```

Verify services are healthy:
```bash
docker compose ps
```

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)


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

## Autonomous Daily Digest (Hermes Cron)

Register the morning job hunt as a recurring Hermes scheduled task (runs daily at 09:00):

```bash
# Register cron (default: 0 9 * * *)
python scripts/hermes_cron_setup.py --register

# Use a custom schedule
python scripts/hermes_cron_setup.py --register --schedule "0 8 * * 1-5"

# List registered cron tasks
python scripts/hermes_cron_setup.py --list

# Remove the scheduled task
python scripts/hermes_cron_setup.py --remove
```

The agent autonomously executes: sync fresh jobs → deduplicate previously alerted postings → score & rank → create daily digest briefing → broadcast activity milestones.

---

## Testing & Verification

The codebase includes an automated test suite covering database operations, normalization logic, deduplication, freshness enforcement, matching algorithms, application prep pipeline, scheduled search, and fault recovery.

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
