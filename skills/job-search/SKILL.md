---
name: job-search
description: "Autonomous multi-strategy job discovery, iterative query planning, and candidate matching for tech jobs in India within 24 hours."
version: 2.0.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, careers, india, search, fresher, ai, agentic-search]
---

# Job Search Skill (Job Agent India)

## Overview
Autonomous, agentic job search and recommendation engine. Decides search strategies (Structured vs Semantic vs Hybrid), asks clarifying questions when critical criteria are missing, refines queries across iterations, avoids infinite search loops, and synthesizes shortlists using deterministic backend ranking.

> [!CRITICAL]
> **Safety Guardrails**:
> - **NEVER** attempt to automatically apply to jobs.
> - Always provide original verified `application_url`.
> - User clicks link and submits application manually.
> - Strictly evaluate only jobs posted within the freshness window (`freshness_hours <= 24` by default).

---

## Agentic Search Decision Framework

```text
User Request
     │
     ▼
Step 1: Inspect Profile & Preferences (`get_candidate_profile`, `get_preferences`)
     │
     ▼
Step 2: Parse Intent & Detect Missing Critical Constraints
     │      ├─ Missing critical info? ──→ Ask user concise clarifying question
     │      └─ Sufficient criteria? ────→ Proceed to Step 3
     ▼
Step 3: Strategy Selection
     ├─ Structured (`search_jobs`): Exact role titles, target locations, experience caps
     ├─ Semantic (`semantic_search_jobs`): Conceptual domains, tech stacks, startup descriptions
     └─ Hybrid: Semantic exploration + Structured filtering
     │
     ▼
Step 4: Iterative Retrieval & Evaluation Loop (Max 3 iterations)
     ├─ Call selected search tool
     ├─ Evaluate yield & relevance
     ├─ Yield insufficient (<3 matches)? Refine query (broaden roles/relax location/switch mode)
     └─ Yield sufficient (>=3 good matches) OR loop count >= 3? STOP loop
     │
     ▼
Step 5: Deterministic Ranking (`rank_jobs`, `match_job`)
     │
     ▼
Step 6: Present Shortlist & Offer Follow-Up Actions
```

---

## Detailed Execution Steps

### Step 1: Candidate Intelligence Context
Always call `get_candidate_profile` (and `get_preferences` if needed) to anchor parameters:
- `target_roles`: Primary search queries (e.g. Backend Developer, AI Engineer).
- `excluded_roles`: Strict negative filters (never recommend these roles).
- `experience_level` & `experience_years`: Experience ceiling (e.g. 0–1 years).
- `skills`: Candidate programming languages, frameworks, and tools.
- `preferred_locations`: Target metro hubs (e.g. Bengaluru, Remote, Gurugram).

### Step 2: Intent Analysis & Clarification Triggers
- Check if user query contains conflicting or ambiguous constraints (e.g., specifying an unfamiliar location while profile mandates Bangalore/Remote).
- If crucial constraint is missing and cannot be inferred from profile (e.g., user asks "find jobs" but has 0 skills and no resume loaded), ask one clear clarifying question before searching.
- If request has sufficient detail or profile is loaded, proceed immediately without unnecessary questions.

### Step 3: Strategy Selection Heuristics
Choose the appropriate tool based on query characteristics:

1. **Structured Search (`search_jobs`)**:
   - Trigger when user asks for standard roles, city names, or experience limits.
   - Example: *"Find entry-level backend roles in Bengaluru or Pune"*.
   - Call parameters:
     ```json
     {
       "roles": ["Backend Developer", "Software Engineer"],
       "locations": ["Bengaluru", "Pune"],
       "experience_max": 1,
       "freshness_hours": 24,
       "include_remote": true,
       "limit": 20
     }
     ```

2. **Semantic Search (`semantic_search_jobs`)**:
   - Trigger when user describes project types, domain problems, or conceptual tech.
   - Example: *"Find companies building AI agent frameworks or multi-modal LLM applications"*.
   - Call parameters:
     ```json
     {
       "query": "AI agent frameworks multi-modal LLM applications",
       "limit": 15,
       "freshness_hours": 24
     }
     ```

3. **Hybrid Search**:
   - Run semantic discovery, extract found job IDs, and cross-reference or backfill with structured filters if results are sparse.

### Step 4: Iterative Refinement & Loop Control
To prevent infinite search loops and unnecessary tool calls, enforce these rules:
- **Maximum 3 search iterations** per user interaction.
- **Sufficiency Condition**: If any iteration returns $\ge 3$ strong matching opportunities, STOP searching and proceed to ranking.
- **Refinement Strategy when yield is low ($< 3$ jobs)**:
  - *Iteration 1*: Exact user query or profile target roles.
  - *Iteration 2 (Broaden)*: Include related adjacent roles (e.g. "Full Stack" &rarr; "Frontend Developer" + "Backend Developer") or set `include_remote: true`.
  - *Iteration 3 (Semantic pivot)*: Use `semantic_search_jobs` with core skills extracted from candidate profile.
- **Never repeat** the identical query or tool arguments.

### Step 5: Ranking & Match Breakdown
1. Extract job UUIDs from search results.
2. Call `rank_jobs`:
   ```json
   {
     "job_ids": ["<uuid-1>", "<uuid-2>", ...]
   }
   ```
3. For the top 1–2 highest scoring positions, call `match_job` if detailed dimension breakdown (skills, location, experience) adds clarity to the final recommendation.

### Step 6: Present Structured Recommendations
For each shortlisted job ($\ge 70\%$ match score), present a crisp card:

```markdown
### 1. [Title] — [Company]
- **Match Score**: [Score]% ([Recommendation Tier])
- **Location**: [Location] ([Remote Type])
- **Experience**: [Experience Range] | **Salary**: [Salary]
- **Posted**: [Age] hours ago (Verified Fresh &le; 24h)
- **Why It Matches**: [Summary from match breakdown]
- **Matched Skills**: [Matched skills list]
- **Missing / Growth Skills**: [Missing skills list]
- **Direct Application Link**: [application_url]
```

### Step 7: Next Steps & Tracking
Offer candidate manual actions:
- "Would you like me to bookmark/save any of these opportunities (`save_job`)?"
- "Once you have applied in your browser, let me know and I will record the tracking status (`update_application_status`)."
