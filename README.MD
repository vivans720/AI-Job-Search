# AI Job Agent India

Personal AI-powered job discovery and recommendation engine for the Indian job market, focused on freshers and entry-level software/AI roles (0–2 years experience) with strict 24-hour freshness and skill-first deterministic matching.

## Key Principles
- **Recall-First Architecture**: Backend never silently discards potentially relevant jobs due to subjective rules (AI score, title/role filter, skill mismatch, experience ceiling >2y, or short snippet length). Strict 24-hour freshness in `Asia/Kolkata` (IST) is the primary eligibility gate.
- **Manual Application Only**: Finds and recommends jobs with verified original application URLs. Never applies automatically.
- **Skill-First Non-Destructive Scoring**: Technical requirements drive 85% of match affinity. Job title and semantic embeddings never inflate scores, but poor matches are scored (not dropped), allowing the candidate full authority.
- **User-Controlled Frontend Filtering**: Experience, skills, and salary filters are client-controlled pills rather than destructive backend gates.
- **Strict 24-Hour Freshness**: Enforced deterministically in backend code (IST, `Asia/Kolkata`), not delegated to LLM prompt.
- **Hybrid Architecture**: PostgreSQL 16 + pgvector in Docker; FastAPI backend, Next.js 15.1 dashboard, and Hermes Agent running locally.
- **Zero Cloud Embedding Cost**: Local dense embeddings via `BAAI/bge-small-en-v1.5` (384-dimensional ONNX runtime).
- **Local LLM Intelligence**: OmniRoute OpenAI-compatible proxy running on port 20128 for resume profiling and skill extraction fallbacks.

---


## Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (tested on Node v24)
- Running instance of OmniRoute (default: `http://localhost:20128/v1`)
- Hermes Agent installed in `~/.hermes`

---

## Quick Start

### Full-Stack Docker Deployment (One Command)
```bash
docker compose up -d
# or: make docker-up
```
Starts `postgres` (pgvector), `redis`, `backend` (FastAPI with auto-migrations), `worker`, and `frontend` (Next.js 15).

Or start individual services manually:

### 1. Start Database Container
```bash
docker compose up -d postgres redis
```


### 2. Configure Environment
```bash
cp .env.example .env
# Active .env is pre-configured for local OmniRoute (port 20128)
```

### 3. Run Backend
```bash
./backend.sh
# or: make backend
```
Verify health:
```bash
curl http://localhost:8000/api/health
# {"status":"ok","database":"connected","pgvector":true}
```

Seed candidate resume:
```bash
backend/.venv/bin/python scripts/seed_candidate_resume.py
```

Sync live fresh jobs from enabled platforms:
```bash
# Sync live fresh jobs from Internshala
backend/.venv/bin/python scripts/sync_internshala.py

# Sync live fresh jobs from Naukri
backend/.venv/bin/python scripts/sync_naukri.py

# Sync live fresh jobs from LinkedIn
backend/.venv/bin/python scripts/sync_linkedin.py

# Sync live fresh jobs via API (All Sources)
curl -X POST "http://localhost:8000/api/v1/jobs/sync?source=all"
```
*(Note: `scripts/seed_sample_jobs.py` is reserved strictly for offline test development fixtures. Live production feeds display 100% authentic scraped listings with zero mock data contamination.)*

### 4. Run Frontend
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Matching Engine & Skill Architecture

The engine uses a **Skill-First Deterministic Model** designed to prevent false positives:

| Dimension | Weight | Description |
|---|---|---|
| **Required Skills** | **65%** | Exact & canonical matches on mandatory requirements |
| **Preferred Skills** | **10%** | Matches on bonus/desirable skills (pro-rated if none required) |
| **Transferable Skills** | **10%** | Partial credit via taxonomy matrix (e.g. Python $\to$ FastAPI at 50%) |
| **Experience Fit** | **5%** | Entry-level (0–2y) and fresher/internship alignment |
| **Location Fit** | **5%** | Preferred city or remote work alignment |
| **Preferences Fit** | **5%** | Salary expectations and target company alignment |
| **Job Title** | **0%** | Evaluated via hard eligibility gating; does not artificially inflate score |
| **Semantic Embedding** | **0%** | Not used to inflate score; reserved for tie-breaking/retrieval |

### Recall-First Scoring & Non-Destructive Ingestion
- **Recall-First Principle**: The backend never silently discards a job because of AI match scores, candidate excluded roles, title mismatch, or missing skills. All fresh jobs (&le;24h) are persisted and returned with `is_excluded = False`.
- **Informational Dimension Eligibility**: Criteria like `experience_eligible` and `location_eligible` are computed as informational breakdown flags and match dimension scores rather than drop gates.
- **Role Ineligibility Gating**: Out-of-domain roles without &ge;80% tech skill match are scored lower (capped at &le;30%), but preserved in the feed so candidates retain full judgment.
- **Non-Destructive Salary Handling**: Positions with undisclosed salaries (`salary_min is None`) are classified as "Not disclosed / Unknown", never assumed unpaid. Explicitly unpaid positions can be filtered by candidate in the frontend.
- **Uncapped Matching Pool**: Eliminates premature SQL `LIMIT` truncation before match evaluation. When sorting by match score, all fresh candidate jobs are evaluated before ranking.

### Job Skill Extraction Service
- **Deterministic First Pass**: Fast, zero-cost regex parsing with word boundaries and section recognition.
- **LLM Fallback**: Invoked via local OmniRoute when descriptions are unstructured, narrative, or have low skill coverage.
- **Anti-Hallucination Guard**: Word boundary verification ensures extracted skills exist in original job text.
- **Soft-Skill Filter**: Discards generic traits (Communication, Teamwork, Problem Solving).
- **Fault-Tolerant**: Non-blocking timeout (10s) with automatic fallback to deterministic extraction.

---

## Live Source Adapters

1. **Internshala (`InternshalaAdapter`)**:
   - Discovers entry-level full-time jobs and paid tech internships across India with category query expansion.
   - **Ephemeral Playwright Camouflage & Dual Gate**: Uses isolated, clean Chromium instances (`--incognito`, `--no-sandbox`) with randomized desktop viewports (1280–1920 $\times$ 720–1080), randomized Chrome versions (`Chrome/{120-131}`), `Asia/Kolkata` timezone, stealth script injection, and explicit cookie clearing (`clear_cookies()`) to prevent perimeter "Account is put on hold" blocks. Paired with resilient HTTP fallback.
   - **False-Positive Account Hold Resolution**: `detect_internshala_block_state` inspects active card containers (`.individual_internship`, `#internship_list_container`) first and strips `#modal_email` template strings, preventing 100% false-positive block aborts on healthy pages.
   - **Anti-Bot Perimeter Guard**: Proactively detects account hold or rules violation pages (`ACCOUNT_HOLD`), cleanly marks `status = "blocked"`, and fails fast to protect IP reputation without crashing multi-source sync.
   - **Timestamp Rescue**: Rescues active relative timestamps ("Just now", "Today", "Active today", "1 day ago") into verified high-confidence UTC timelines while strictly excluding stale posts (>24h). Decouples internship duration from posting dates.
2. **Naukri (`NaukriAdapter`)**:
   - **Next.js Static Data Layer Extraction (`__NEXT_DATA__`)**: Directly extracts raw JSON payloads from embedded Next.js script tags, guaranteeing 100% data fidelity and total immunity to CSS selector drift, with DOM card parsing as fallback.
   - **Dynamic Experience Floor Normalization**: Resolves the experience ceiling trap on broad ranges (`0-5 Yrs`, `0-4 Yrs`, `1-4 Yrs`). When a position accepts early-career applicants (`exp_min <= 1`), entry-level opportunities survive downstream experience filters.
   - **Deterministic Process Lifecycle**: Eliminates Chrome zombie thread leaks via strict `asyncio.wait_for` timeouts coupled with explicit `proc.kill()` and `proc.wait()` cleanup guardrails.
   - **Experience String Blindness Fix**: Avoids forced `&experience=0` queries that limit results strictly to literal "Fresher" tags, allowing 0–2y early career postings to enter the pipeline.
3. **LinkedIn (`LinkedInAdapter`)**:
    - Triple Discovery Engine: Primary fast path via unauthenticated public guest API (`/jobs-guest/jobs/api/seeMoreJobPostings/search`) targeting postings &le;24 hours (`f_TPR=r86400`).
    - Rendered path via shared Crawl4AI provider (`CrawlerProvider` boundary, `_fetch_via_crawl4ai`), used when guest API misses. Verified working against `example.com`; LinkedIn perimeter currently slow/blocks rendered fetches, so this path degrades gracefully.
    - Final fallback path: Playwright headless browser automation leveraging stealth camouflage (`apply_stealth_context`).
   - **Guest API Snippet Hydration & Fallback**: Fetches full job details via lightweight HTTP endpoint for shallow guest cards (`desc_len < 200`). If hydration fails or snippet remains short, retains the job with `description_confidence = "LOW"`.
   - **Relative Recency Prioritization**: Prioritizes exact relative posting strings ("10 hours ago", "14 hours ago", "22 hours ago") anchored to `scraped_at` over date-only timestamps, preventing false-positive stale rejections from artificial midnight offsets.
   - Resilient networking: Built-in local Tor SOCKS5 network proxy fallback (`socks5://127.0.0.1:9050`) on HTTP `429` rate limits or `403` anti-bot blocks.
4. **Crawl4AI Infrastructure (`Crawl4AICrawlerProvider`, `crawl4ai==0.9.3`)**:
    - Universal `CrawlerProvider` abstraction (`backend/app/crawling/`) decoupled from concrete crawler implementations.
    - Powered by Crawl4AI `AsyncWebCrawler` with concurrency bounding (`asyncio.Semaphore(3)`), page timeouts, and schema-driven `JsonCssExtractionStrategy` for structured card/field parsing.
    - Used by LinkedIn rendered fallback path. Internshala and Naukri retain custom resilient HTTP/Playwright paths. Health probe at `GET /api/v1/sources/health` reports status truthfully.

### Multi-Source Live Sync
- **Interactive UI**: Dashboard (`/dashboard`) and Jobs Feed (`/jobs`) feature source selectors to trigger on-demand sync across `All Sources`, `Internshala`, `Naukri`, or `LinkedIn`.
- **Candidate Target-Role Focused**: Automatically targets active roles from the candidate profile to optimize crawling speed and relevance.
- **Fail-Safe Session Rollback**: Database transactions rollback cleanly on any source error via `sync_source_isolated` / `sync_all_isolated`, ensuring other adapters sync without interruption.
- **Structured Status Response**: Sync API returns composite `status` (`success`, `partial_success`, `blocked`, `failed`) and granular per-source report under `sources` detailing discovered, accepted, and error context.

---

## Scraping Engine Hardening & Free Anti-Bot Architecture

To ingest from global enterprise platforms (LinkedIn, Wellfound, Instahyre) without IP bans or expensive proxy services, the backend foundation includes 5 mandatory protection layers:

1. **Local Browser Fingerprint Camouflage (`app/utils/browser_stealth.py`)**:
   - Strips `navigator.webdriver` (returns `undefined`).
   - Injects realistic `window.chrome = { runtime: {} }` and mock `navigator.plugins`.
   - Emulates native Indian language preferences (`['en-IN', 'en-US', 'en']`).
   - Dynamic viewport randomization: assigns random desktop geometries (1366–1920 &times; 768–1080).
   - Standard desktop User-Agent and `Accept-Language` headers.

2. **Shared Local Session Persistence (`app/utils/browser_context.py`)**:
   - Replaces fragile ephemeral browser contexts with `playwright.chromium.launch_persistent_context()`.
   - Binds to a persistent local hidden profile: `~/.config/job_agent_browser_profile`.
   - **Interactive Login CLI**: Run `python -m app.utils.browser_context --login <URL>` once in visible mode to solve CAPTCHAs and log in manually. Headless scrapers reuse those exact saved cookies indefinitely.

3. **Free Local Tor SOCKS5 Network Proxy Fallback (`app/utils/http_client.py`)**:
   - Socket-level probe (`is_tor_proxy_available` on `127.0.0.1:9050`, 0.3s timeout).
   - Primary traffic routes through direct home WAN interface.
   - On persistent rate limits (`429`) or anti-bot blocks (`403`, `406`), automatically re-routes requests through the local Tor SOCKS5 proxy without paid proxy subscriptions.

4. **Resource Interception & Content Rejection Filters (`app/utils/browser_stealth.py`)**:
   - Playwright route filter (`page.route("**/*", ...)`) aborting heavy media formats (`.png`, `.jpg`, `.woff2`, `.ttf`, `.mp4`).
   - Aborts analytics and telemetry beacons (Google Analytics, Datadog, Hotjar, DoubleClick, Segment, Clarity).
   - Reduces RAM/bandwidth usage by up to 70% and accelerates page load times.

5. **Schema.org JSON-LD Structural Extraction Channel (`app/utils/json_ld.py`)**:
   - Parses `<script type="application/ld+json">` containers directly from page HTML.
   - Extracts canonical Schema.org `JobPosting` fields (title, company, description, datePosted, salary, location, remote type).
   - Falls back gracefully to fragile CSS selectors only when structured metadata is absent.

---

## Hermes Agent MCP Connection

Register the FastMCP server with your local Hermes Agent:
```bash
~/.hermes/hermes-agent/venv/bin/hermes mcp add job-agent-india \
  --command "$(pwd)/backend/.venv/bin/python" \
  --args "$(pwd)/mcp-server/server.py"
```

Test connection:
```bash
~/.hermes/hermes-agent/venv/bin/hermes mcp test job-agent-india
```

### Available MCP Tools (10)
- `get_candidate_profile`: Retrieve skills, experience, target and excluded roles.
- `search_jobs`: Query fresh jobs strictly bounded by &le;24h posting age.
- `get_job`: Retrieve full job details with verified original application URL.
- `match_job`: Evaluate 6-dimension deterministic match against candidate profile.
- `rank_jobs`: Rank multiple job IDs by match score.
- `save_job` / `ignore_job`: Bookmark or dismiss opportunities.
- `update_application_status`: Track manual application progress (`DISCOVERED` &rarr; `APPLIED` &rarr; `OFFER`).
- `get_saved_jobs`: View bookmarked and applied jobs.
- `get_search_history`: Review recent searches and discovery stats.

### Installed Hermes Skills (3)
- `job-search`: 5-step autonomous discovery loop via MCP and OmniRoute.
- `daily-digest`: Morning briefing of top fresh matches.
- `pipeline-tracker`: Application tracking and status progression.

---

## Key Backend Endpoints

- `GET /api/health` — Database and pgvector healthcheck probe.
- `GET /api/v1/sources/health` — Live connectivity and health probe across all registered source adapters (`internshala`, `naukri`, `linkedin`) and crawling infrastructure (`infrastructure.crawl4ai`).
- `GET /api/v1/sources/history` — Audit trail of recent multi-source sync runs from JSONL persistent log.
- `GET /api/v1/resumes/active` — Retrieve latest active parsed resume profile.
- `GET /api/v1/jobs` — Fresh job search strictly bounded &le;24h with deterministic skill-first scoring and automatic exclusion of saved, tracked, and rejected jobs (`exclude_rejected=true`).
- `POST /api/v1/jobs/{job_id}/status` — Update tracking status (`SAVED`, `REJECTED`, `APPLIED`, etc.) with instant discovery feed synchronization.
- `GET /api/v1/dashboard/stats` — Real-time aggregate statistics for candidate dashboard (excludes saved and rejected jobs from fresh recommendations).
- `POST /api/v1/agent/briefing` — AI Morning Executive Briefing powered by OmniRoute LLM and top fresh matches (excludes saved and rejected jobs).
- `POST /api/v1/jobs/sync?source=all` — On-demand live multi-source ingestion across all enabled boards (Internshala, Naukri, LinkedIn).
- `POST /api/v1/jobs/sync?source=internshala|naukri|linkedin` — On-demand live ingestion for a specific job board or multi-source engine.
- `GET /PUT /api/v1/profile` — Candidate profile retrieval and manual override management.
- `GET /PUT /api/v1/preferences` — Search criteria, match threshold, and priority/exclusion lists.

---

## Testing & Verification
 
Run backend unit and integration test suite:
```bash
# Full test suite (189 tests across 25 suites)
backend/.venv/bin/pytest tests/ -v
# or: make test
```

Frontend production build check:
```bash
cd frontend && npm run build
# 13/13 static pages compiled successfully (0 errors, 0 warnings)
```

---

## Documentation Links

- [Development & Onboarding Guide](docs/development_guide.md)
- [Architecture Overview](docs/architecture.md)
- [AI & Matching Engine Formulation](docs/ai_architecture.md)
- [Crawling, Scraping & Ingestion Pipeline](docs/crawling_and_ingestion.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [License (MIT)](LICENSE)
