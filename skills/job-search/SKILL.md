---
name: job-search
description: "Autonomous multi-strategy job discovery, iterative query planning, persistent preference memory, and candidate matching for tech jobs in India within 24 hours."
version: 2.1.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, careers, india, search, fresher, ai, agentic-search, persistent-memory]
---

# Job Search Skill (Job Agent India)

## Overview
Autonomous, agentic job search, recommendation engine, and personalized career assistant. Combines persistent user preference memory (`USER.md` / `MEMORY.md`), multi-strategy search planning (Structured vs Semantic vs Hybrid), conversational clarification, iterative query refinement, and deterministic backend ranking.

> [!CRITICAL]
> **Safety Guardrails**:
> - **NEVER** attempt to automatically apply to jobs.
> - Always provide original verified `application_url`.
> - User clicks link and submits application manually.
> - Strictly evaluate only jobs posted within the freshness window (`freshness_hours <= 24` by default).

---

## Architecture & Memory Separation of Concerns

```text
┌────────────────────────────────────────────────────────┐
│                   HERMES AGENT                         │
│                                                        │
│  ┌─────────────────────────┐  ┌─────────────────────┐  │
│  │   USER PROFILE: USER.md │  │ NOTES: MEMORY.md    │  │
│  │   - Role preferences    │  │ - Search nuances    │  │
│  │   - Culture & team fit  │  │ - Tool conventions  │  │
│  │   - Disliked domains    │  │ - Environment facts │  │
│  │   (<= 1,375 chars)      │  │ (<= 2,200 chars)    │  │
│  └─────────────────────────┘  └─────────────────────┘  │
└───────────────┬──────────────────────────┬─────────────┘
                │                          │
                ▼ MCP                      ▼ Native tool
      ┌──────────────────┐       ┌──────────────────────┐
      │  Job Search MCP  │       │ memory(action=...,   │
      │  Server Tools    │       │        target=...,   │
      └─────────┬────────┘       │        content=...)  │
                │                └──────────────────────┘
                ▼
      ┌──────────────────┐
      │    POSTGRESQL    │  <-- Single source of truth for
      │    + pgvector    │      structured data (jobs,
      └──────────────────┘      applications, profiles, prefs)
```

### Strict Storage Boundaries:
1. **Hermes Memory (`USER.md` / `MEMORY.md`)**:
   - Store **only** qualitative, behavioral preferences and learnings (e.g., *"Prefers early-stage GenAI startups over service companies"*, *"Dislikes unpaid internships"*, *"Prefers Bangalore/Remote"*).
   - Each entry must be concise and declarative (<200 characters).
   - **NEVER** store job IDs, raw application state, or long job descriptions in memory.
2. **PostgreSQL / pgvector**:
   - Stores all jobs, raw candidate resumes, application tracking statuses, and structured filter limits (`experience_max_years`, `freshness_hours`).

---

## Agentic Search Decision Framework

```text
User Request
     │
     ▼
Step 1: Context & Preference Evaluation
     ├─ Read Hermes system prompt snapshot (`USER PROFILE` / `MEMORY`)
     ├─ Call MCP tools: `get_candidate_profile`, `get_preferences`
     └─ Merge behavioral memory with structured profile parameters
     │
     ▼
Step 2: Preference Learning & Sync
     ├─ User stated explicit preference/dislike?
     │    ├─ Update `user` memory: `memory(action="add"|"replace", target="user", ...)`
     │    └─ Structured field changed? Call MCP `update_preferences(...)`
     │
     ▼
Step 3: Parse Intent & Detect Missing Critical Constraints
     ├─ Missing critical info? ──→ Ask user concise clarifying question
     └─ Sufficient criteria? ────→ Proceed to Step 4
     │
     ▼
Step 4: Strategy Selection
     ├─ Structured (`search_jobs`): Exact role titles, target locations, experience caps
     ├─ Semantic (`semantic_search_jobs`): Conceptual domains, tech stacks, startup descriptions
     └─ Hybrid: Semantic exploration + Structured filtering
     │
     ▼
Step 5: Iterative Retrieval & Evaluation Loop (Max 3 iterations)
     ├─ Call selected search tool with preference filters applied
     ├─ Evaluate yield & relevance against candidate preferences
     ├─ Yield insufficient (<3 matches)? Refine query (broaden roles/relax location/switch mode)
     └─ Yield sufficient (>=3 good matches) OR loop count >= 3? STOP loop
     │
     ▼
Step 6: Deterministic Ranking (`rank_jobs`, `match_job`)
     │
     ▼
Step 7: Present Shortlist & Offer Follow-Up Actions
```

---

## Detailed Execution Steps

### Step 1: Candidate Intelligence & Memory Context
1. Inspect the frozen system prompt memory block:
   - Check `USER PROFILE (USER.md)` for personal preferences, work mode desires, company dislikes, or salary expectations.
   - Check `MEMORY (MEMORY.md)` for environmental conventions or past search notes.
2. Call MCP `get_candidate_profile` and `get_preferences`:
   - `target_roles`: Primary search queries (e.g. Backend Developer, AI Engineer).
   - `excluded_roles`: Strict negative filters (merge with negative preferences in `USER.md`).
   - `experience_level` & `experience_years`: Experience ceiling (e.g. 0–1 years).
   - `skills`: Candidate programming languages, frameworks, and tools.
   - `preferred_locations`: Target metro hubs (e.g. Bengaluru, Remote, Gurugram).

### Step 2: Preference Learning & Bi-directional Reconciliation
When the user expresses an explicit preference (e.g., *"I don't want to work in edtech"*, *"Focus only on remote AI agent roles"*, *"I prefer Bangalore over Pune"*):
1. **Record in Hermes Memory**:
   - Use the native `memory` tool:
     ```python
     # Example: User states a new preference
     memory(action="add", target="user", content="Prefers AI agent & developer tooling startups in Bangalore/Remote. Avoid edtech.")
     ```
   - If an existing entry conflicts, update it using `replace`:
     ```python
     memory(action="replace", target="user", old_text="Bangalore/Remote", content="Prefers Bangalore, Hyderabad, or Remote roles.")
     ```
   - Keep entries under 200 characters to preserve the 1,375 character limit.
2. **Reconcile with Structured Database**:
   - If the preference affects structured parameters (e.g., locations, freshness, max experience), call MCP `update_preferences`:
     ```json
     {
       "updates": {
         "preferred_locations": ["Bengaluru", "Hyderabad", "Remote"],
         "excluded_companies": ["EdTechCo"]
       }
     }
     ```

### Step 3: Intent Analysis & Clarification Triggers
- Evaluate if user request conflicts with saved preferences or profile constraints.
- If a critical constraint is missing and cannot be resolved from `USER.md` or profile, ask one concise clarifying question before searching.
- If request and profile provide clear parameters, proceed directly to search without delay.

### Step 4: Strategy Selection Heuristics
Choose search tool dynamically based on query characteristics and user preferences:

1. **Structured Search (`search_jobs`)**:
   - Used for specific role titles, city names, or experience limits.
   - Inject preferences (e.g., filtered locations, roles).
   - Example:
     ```json
     {
       "roles": ["Backend Developer", "AI Engineer"],
       "locations": ["Bengaluru", "Remote"],
       "experience_max": 1,
       "freshness_hours": 24,
       "include_remote": true,
       "limit": 20
     }
     ```

2. **Semantic Search (`semantic_search_jobs`)**:
   - Used when user describes conceptual projects, tech stacks, or domains.
   - Example:
     ```json
     {
       "query": "Autonomous AI agents LLM orchestration FastAPI pgvector",
       "limit": 15,
       "freshness_hours": 24
     }
     ```

3. **Hybrid Search**:
   - Run semantic query, extract relevant job IDs, cross-reference against structured preferences, and backfill with structured search if results are sparse.

### Step 5: Iterative Refinement & Loop Control
To avoid infinite search loops while guaranteeing high-quality results:
- **Maximum 3 search iterations** per session.
- **Sufficiency Condition**: If any iteration yields $\ge 3$ strong matching opportunities, STOP searching and proceed to ranking.
- **Refinement Strategy when yield is low ($< 3$ jobs)**:
  - *Iteration 1*: Exact user query + target roles from profile/memory.
  - *Iteration 2 (Broaden)*: Broaden role titles or add `include_remote: true`.
  - *Iteration 3 (Semantic pivot)*: Use `semantic_search_jobs` using candidate core skills and domain interests from memory.
- **Never repeat** identical parameters.

### Step 6: Ranking & Match Breakdown
1. Extract job UUIDs from search results.
2. Call `rank_jobs`:
   ```json
   {
     "job_ids": ["<uuid-1>", "<uuid-2>", ...]
   }
   ```
3. Filter out any opportunities that violate user preference memory (e.g. excluded domains/companies).
4. For top 1–2 jobs, call `match_job` to extract rich multi-dimensional justification.

### Step 7: Present Structured Recommendations
For each shortlisted job ($\ge 70\%$ match score), present a crisp card:

```markdown
### 1. [Title] — [Company]
- **Match Score**: [Score]% ([Recommendation Tier])
- **Location**: [Location] ([Remote Type])
- **Experience**: [Experience Range] | **Salary**: [Salary]
- **Posted**: [Age] hours ago (Verified Fresh <= 24h)
- **Why It Matches**: [Summary incorporating candidate skills & preferences]
- **Matched Skills**: [Matched skills list]
- **Missing / Growth Skills**: [Missing skills list]
- **Direct Application Link**: [application_url]
```

### Step 8: Next Steps & Tracking
Offer candidate manual actions:
- "Would you like me to bookmark/save any of these opportunities (`save_job`)?"
- "Once you have applied in your browser, let me know and I will record the tracking status (`update_application_status`)."
- "Would you like me to remember any specific company or role preference from this search (`memory`)?"
