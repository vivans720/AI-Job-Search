---
name: daily-digest
description: "Generate a morning briefing of fresh job opportunities posted in the last 24 hours."
version: 1.0.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, digest, morning-briefing, summary, india]
---

# Daily Job Digest Skill

## Overview
Compiles a concise, high-signal morning executive briefing of all fresh tech jobs discovered in India over the past 24 hours.

---

## Workflow

1. Call `get_candidate_profile` to retrieve target roles, skills, and current excluded roles.
2. Call `search_jobs` with `freshness_hours: 24` and `limit: 30`.
3. Call `rank_jobs` to order results by match score.
4. Filter out any jobs marked `SKIP` or below the user's match threshold (default: 70%).
5. Output the Daily Digest format:

```markdown
# 🌅 Daily Tech Job Digest — [Date]
**Active Fresh Feed**: Opportunities posted strictly within the last 24 hours.

## Top Recommendations For You

### 1. [Title] @ [Company] ([Match Score]%)
- **Location**: [Location] | **Salary**: [Salary]
- **Key Fit**: [1-sentence match explanation]
- **Apply URL**: [Direct link]

### 2. [Title] @ [Company] ([Match Score]%)
...

## Summary Statistics
- Fresh Opportunities Found: [Count]
- Strong Matches (&ge;80%): [Count]
- Target Roles Covered: [Role List]

👉 *Remember: Click links to apply manually in your browser. Tell me to mark as APPLIED when submitted.*
```
