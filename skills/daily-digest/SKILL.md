---
name: daily-digest
description: "Generate a morning briefing of fresh job opportunities posted in the last 24 hours with duplicate prevention and zero-match guidance."
version: 2.0.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, digest, morning-briefing, summary, india, autonomous-cron]
---

# Daily Job Digest Skill

## Overview
Compiles a concise, high-signal morning executive briefing of fresh tech jobs discovered in India over the past 24 hours. Features strict duplicate prevention, zero-match day handling, and persistent candidate feed recording.

---

## Workflow

1. **Candidate Context**:
   - Call `get_candidate_profile` to retrieve target roles, core skills, and excluded roles.
   - Call `get_preferences` for preferred locations, source boards, and `match_threshold` (default: 60%).
   - Inspect qualitative preferences in Hermes memory (`USER.md`).

2. **Fresh Search with Deduplication**:
   - Call `search_jobs` with `freshness_hours: 24`, target roles, and preferred locations.
   - The backend automatically omits previously notified postings, saved jobs, applied jobs, and dismissed jobs.
   - Call `notify_activity(message="Scanning fresh opportunities posted in last 24 hours", category="analyzing")`.

3. **Scoring & Ranking**:
   - Call `rank_jobs` to evaluate and sort opportunities by match score.
   - Filter jobs meeting or exceeding candidate `match_threshold`.
   - Call `notify_activity(message="Evaluating multi-dimensional match scores", category="filtering")`.

4. **Construct & Record Digest**:
   - If $\ge 1$ strong matches exist:
     - Format top 3–5 recommendations.
     - Call `create_daily_digest(summary=..., job_ids=[...], status="DELIVERED")`.
   - If **zero matches** meet the threshold:
     - Generate an informative Zero-Match Daily Briefing explaining that no fresh postings passed the threshold in the last 24 hours.
     - Offer actionable suggestions (e.g. relaxing threshold by 5–10% or adding remote tags).
     - Call `create_daily_digest(summary=..., job_ids=[], status="NO_MATCHES")`.

5. **Output Format**:

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
- Strong Matches (≥[Threshold]%): [Count]
- Target Roles Covered: [Role List]

👉 *Remember: Click links to apply manually in your browser. Tell me to mark as APPLIED when submitted.*
```
