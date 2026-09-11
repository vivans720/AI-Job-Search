---
name: pipeline-tracker
description: "Manage candidate application pipeline and update tracking status."
version: 1.0.0
author: Job Agent India
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jobs, tracking, pipeline, applications, kanban]
---

# Job Application Pipeline Tracker Skill

## Overview
Assists the candidate in tracking manual applications through the hiring pipeline:
`DISCOVERED` &rarr; `SAVED` &rarr; `VIEWED` &rarr; `APPLIED` &rarr; `INTERVIEW` &rarr; `OFFER` (or `REJECTED` / `IGNORED`).

> [!IMPORTANT]
> The candidate applies manually. The agent never submits applications on behalf of the user.

---

## Workflow

### 1. View Current Applications
Call `get_saved_jobs`:
- If the user asks for all jobs: `get_saved_jobs()`
- If the user asks for applied jobs: `get_saved_jobs(status="APPLIED")`
- If the user asks for saved/bookmarked: `get_saved_jobs(status="SAVED")`

### 2. Update Job Status
When user states "I applied to Razorpay" or "I got an interview with Sarvam AI":
1. Find the job ID from `get_saved_jobs` or recent search results.
2. Call `update_application_status(job_id="<id>", status="<STATUS>", notes="<optional-user-notes>")`.
3. Confirm update to the user with date and current stage.
