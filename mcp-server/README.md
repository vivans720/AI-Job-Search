# Job Agent India — MCP Server

Model Context Protocol (MCP) server providing structured tools for the **Hermes Agent** to interact with the candidate profile, fresh job database, deterministic matching engine, and manual application tracker.

---

## 1. Exposed Tools

| Tool | Purpose |
|---|---|
| `get_candidate_profile` | Returns structured candidate profile (skills, target roles, experience, manual overrides). |
| `search_jobs` | Search for fresh opportunities (strictly &le;24 hours). Never returns stale jobs. |
| `get_job` | Get full details of a specific job by ID (includes original application URL). |
| `match_job` | Calculate 6-dimension match breakdown against candidate profile. |
| `rank_jobs` | Rank a list of job IDs by calculated match score descending. |
| `save_job` | Bookmark a job to candidate's saved list for manual application. |
| `ignore_job` | Mark a job as ignored to hide from future recommendations. |
| `update_application_status` | Update manual status (`DISCOVERED`, `SAVED`, `VIEWED`, `APPLIED`, `INTERVIEW`, `REJECTED`, `OFFER`, `IGNORED`). |
| `get_saved_jobs` | List saved jobs and tracked applications. |
| `get_search_history` | Retrieve recent searches and discovery/freshness statistics. |

> [!CAUTION]
> **Strict Guardrails Enforced**:
> - Zero automatic application tools (`apply_job`, `submit_application`, `auto_apply` do **NOT** exist).
> - Opening an application URL or viewing a job never marks it as `APPLIED`.
> - Candidate applies manually in external browser tabs.

---

## 2. Registering with Hermes Agent

Hermes Agent is installed in `~/.hermes`. Connect this MCP server using the stdio transport:

```bash
~/.hermes/hermes-agent/venv/bin/hermes mcp add job-agent-india \
  --command "$(pwd)/backend/.venv/bin/python" \
  --args "$(pwd)/mcp-server/server.py"
```

Verify registration:
```bash
~/.hermes/hermes-agent/venv/bin/hermes mcp list
```

Test connection:
```bash
~/.hermes/hermes-agent/venv/bin/hermes mcp test job-agent-india
```

---

## 3. Running Standalone for Testing

Run stdio server directly:
```bash
backend/.venv/bin/python mcp-server/server.py
```

Run test suite:
```bash
backend/.venv/bin/pytest tests/test_mcp_server.py -v
```
