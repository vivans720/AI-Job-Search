import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sync_log.jsonl"


def log_sync_event(stats: dict[str, Any], log_file: Path | None = None) -> dict[str, Any]:
    """
    Appends a structured sync execution record into an append-only JSON Lines file.
    Does not crash on filesystem issues; logs gracefully.
    """
    target = log_file or DEFAULT_LOG_FILE
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": stats.get("source", "unknown"),
        "status": stats.get("status", "success"),
        "error": stats.get("error"),
        "error_category": stats.get("error_category"),
        "duration_ms": stats.get("duration_ms", 0.0),
        "retries_count": stats.get("retries_count", 0),
        "total_discovered": stats.get("total_discovered", 0),
        "filtered_by_validation": stats.get("filtered_by_validation", 0),
        "filtered_by_freshness": stats.get("filtered_by_freshness", 0),
        "fresh_jobs": stats.get("fresh_jobs", 0),
        "filtered_by_experience": stats.get("filtered_by_experience", 0),
        "eligible_candidates": stats.get("eligible_candidates", 0),
        "deduplicated": stats.get("deduplicated", 0),
        "canonical_saved": stats.get("canonical_saved", 0),
        "updated_existing": stats.get("updated_existing", 0),
        "saved_jobs": stats.get("saved_jobs", 0),
        "saved_internships": stats.get("saved_internships", 0),
        "metrics": stats.get("metrics", {}),
    }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("sync_audit_logged", source=entry["source"], target=str(target))
    except Exception as e:
        logger.warning("sync_audit_log_failed", error=str(e), path=str(target))

    return entry


def get_recent_sync_logs(limit: int = 50, log_file: Path | None = None) -> list[dict[str, Any]]:
    """
    Reads the most recent sync entries from the audit log (latest first).
    """
    target = log_file or DEFAULT_LOG_FILE
    if not target.exists():
        return []

    entries = []
    try:
        with target.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:][::-1]
    except Exception as e:
        logger.warning("read_sync_logs_failed", error=str(e))
        return []
