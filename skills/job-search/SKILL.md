---
name: job-search
description: "Discover, match, and recommend fresh tech jobs in India within 24 hours."
version: 1.0.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, careers, india, search, fresher, ai]
---

# Job Search Skill (Job Agent India)

## Overview
Autonomous job discovery and deterministic recommendation for entry-level, fresher, and software/AI engineering opportunities in the Indian job market.

> [!CRITICAL]
> **Safety Guardrails**:
> - **NEVER** attempt to automatically apply to jobs.
> - Always present the original verified `application_url`.
> - The user must click the link and submit applications manually.
> - Strictly evaluate only jobs posted within the last 24 hours (`freshness_hours <= 24`).

---

## Tool Workflow

### Step 1: Load Candidate Intelligence
Always call `get_candidate_profile` first.
Read:
- `target_roles`: Primary search queries (e.g. Full Stack Developer, Backend Developer, AI Engineer).
- `excluded_roles`: Strict negative filters (never recommend these roles).
- `experience_level` & `experience_years`: Experience ceiling (e.g. 0–1 years).
- `skills`: Candidate's programming languages, frameworks, and databases.
- `preferred_locations`: Target cities (e.g. Bengaluru, Remote, Gurugram).

### Step 2: Search Fresh Opportunities
Call `search_jobs` using the candidate's target roles and preferred criteria:
```json
{
  "roles": ["Full Stack Developer", "Backend Developer", "AI Engineer"],
  "locations": ["Bengaluru", "Remote"],
  "experience_max": 1,
  "freshness_hours": 24,
  "include_remote": true,
  "limit": 20
}
```

### Step 3: Rank & Evaluate Matches
Call `rank_jobs` with the discovered job IDs to obtain deterministic 6-dimension scoring:
```json
{
  "job_ids": ["<id-1>", "<id-2>", ...]
}
```
If detailed breakdown is needed for a top candidate, call `match_job` on specific job IDs.

### Step 4: Present Recommendations to Candidate
For each recommended job (&ge; 70% match score), present a structured card:

```markdown
### 1. [Title] — [Company]
- **Match Score**: [Score]% ([Recommendation Tier])
- **Location**: [Location] ([Remote Type])
- **Experience**: [Experience Range] | **Salary**: [Salary]
- **Posted**: [Age] hours ago (Verified Fresh &le; 24h)
- **Why It Matches**: [Brief explanation from match breakdown]
- **Matched Skills**: [Matched skills list]
- **Missing / Growth Skills**: [Missing skills list]
- **Direct Application Link**: [application_url]
```

### Step 5: Offer Manual Actions
Ask the user:
- "Would you like me to bookmark/save any of these opportunities (`save_job`)?"
- "Once you have applied in your browser, let me know and I will update the tracking status (`update_application_status`)."
