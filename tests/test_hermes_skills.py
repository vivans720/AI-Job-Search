from pathlib import Path
import pytest
import yaml


def parse_skill_frontmatter(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8")
    parts = content.split("---")
    assert len(parts) >= 3, "Invalid SKILL.md structure: missing frontmatter delimiters"
    return yaml.safe_load(parts[1])


def test_job_search_skill_frontmatter():
    skill_path = Path("skills/job-search/SKILL.md")
    assert skill_path.exists()
    fm = parse_skill_frontmatter(skill_path)
    assert fm["name"] == "job-search"
    assert "description" in fm
    assert "hermes" in fm.get("metadata", {})
    assert "jobs" in fm["metadata"]["hermes"]["tags"]


def test_daily_digest_skill_frontmatter():
    skill_path = Path("skills/daily-digest/SKILL.md")
    assert skill_path.exists()
    fm = parse_skill_frontmatter(skill_path)
    assert fm["name"] == "daily-digest"
    assert "description" in fm


def test_pipeline_tracker_skill_frontmatter():
    skill_path = Path("skills/pipeline-tracker/SKILL.md")
    assert skill_path.exists()
    fm = parse_skill_frontmatter(skill_path)
    assert fm["name"] == "pipeline-tracker"
    assert "description" in fm


def test_installed_hermes_skills():
    home = Path.home()
    hermes_skills = home / ".hermes" / "skills" / "productivity"
    assert (hermes_skills / "job-search" / "SKILL.md").exists()
    assert (hermes_skills / "daily-digest" / "SKILL.md").exists()
    assert (hermes_skills / "pipeline-tracker" / "SKILL.md").exists()
