import subprocess
import yaml
from pathlib import Path
import pytest


def test_hermes_config_paths():
    config_path = Path.home() / ".hermes" / "config.yaml"
    assert config_path.exists(), "Hermes config file not found"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    mcp_servers = config.get("mcp_servers", {})
    assert "job-agent-india" in mcp_servers, "job-agent-india not in mcp_servers"

    server_conf = mcp_servers["job-agent-india"]
    assert server_conf.get("enabled") is True

    python_bin = Path(server_conf["command"])
    assert python_bin.exists(), f"Python binary does not exist: {python_bin}"
    assert "Production Job Search AI" in str(python_bin)

    server_script = Path(server_conf["args"][0])
    assert server_script.exists(), f"Server script does not exist: {server_script}"
    assert "Production Job Search AI" in str(server_script)


def test_hermes_mcp_cli_test_command():
    res = subprocess.run(
        ["hermes", "mcp", "test", "job-agent-india"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert res.returncode == 0
    assert "Connected" in res.stdout or "connected" in res.stdout
    assert "get_candidate_profile" in res.stdout
    assert "get_preferences" in res.stdout
    assert "search_jobs" in res.stdout
    assert "semantic_search_jobs" in res.stdout
    assert "get_job" in res.stdout


@pytest.mark.asyncio
async def test_read_tools_direct():
    import sys
    mcp_dir = str(Path(__file__).resolve().parent.parent / "mcp-server")
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    from tools.profile_tools import handle_get_candidate_profile, handle_get_preferences
    from tools.search_tools import handle_search_jobs

    profile = await handle_get_candidate_profile()
    assert isinstance(profile, dict)

    prefs = await handle_get_preferences()
    assert isinstance(prefs, dict)
    assert "freshness_hours" in prefs

    search_res = await handle_search_jobs(limit=3, freshness_hours=48)
    assert isinstance(search_res, dict)
    assert "fresh_jobs_found" in search_res
