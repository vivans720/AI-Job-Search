import json
import pytest
from app.utils.sync_logger import log_sync_event, get_recent_sync_logs


def test_log_sync_event_and_retrieve(tmp_path):
    log_file = tmp_path / "test_sync.jsonl"

    stats_1 = {
        "source": "internshala",
        "total_discovered": 20,
        "filtered_by_validation": 1,
        "canonical_saved": 8,
    }
    stats_2 = {
        "source": "naukri",
        "total_discovered": 35,
        "filtered_by_validation": 0,
        "canonical_saved": 12,
    }

    log_sync_event(stats_1, log_file=log_file)
    log_sync_event(stats_2, log_file=log_file)

    assert log_file.exists()
    lines = [json.loads(line) for line in log_file.read_text().splitlines() if line]
    assert len(lines) == 2
    assert lines[0]["source"] == "internshala"
    assert lines[1]["source"] == "naukri"

    # Test reading logs in reverse chronological order
    recent = get_recent_sync_logs(limit=10, log_file=log_file)
    assert len(recent) == 2
    assert recent[0]["source"] == "naukri"
    assert recent[1]["source"] == "internshala"
