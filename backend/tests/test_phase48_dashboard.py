import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.dashboard_service import get_dashboard_data, _get_greeting
from app.models.candidate_profile import CandidateProfile
from app.models.preference import Preference
from app.schemas.job import JobListItem
from app.schemas.match import MatchBreakdown


def test_greeting_logic():
    greeting = _get_greeting()
    assert greeting in ["Good morning", "Good afternoon", "Good evening", "Good night"]


@pytest.mark.asyncio
async def test_get_dashboard_data_structure():
    user_id = uuid.uuid4()
    profile = CandidateProfile(
        id=user_id,
        skills=["Python", "FastAPI"],
    )
    pref = Preference(user_id=user_id, preferred_technologies=["Python", "FastAPI"])

    mock_db = AsyncMock()

    # Mock DB queries:
    # 1. fresh jobs count
    res_fresh = MagicMock()
    res_fresh.scalar_or_none.return_value = 1284

    # 2. application status count
    res_status = MagicMock()
    res_status.all.return_value = [("SAVED", 10), ("APPLIED", 4), ("INTERVIEWING", 1)]

    mock_db.execute.side_effect = [res_fresh, res_status]

    mock_scored = [
        JobListItem(
            id="job-1",
            title="Backend Lead",
            company="Tech Co",
            location="Remote",
            source="linkedin",
            application_url="https://example.com/job1",
            required_skills=["Python", "FastAPI", "Docker", "Kubernetes"],
            match=MatchBreakdown(
                overall_score=92.0,
                skill_score=90.0,
                matched_skills=["Python", "FastAPI"],
                missing_skills=["Docker", "Kubernetes"],
                recommendation="STRONG_MATCH"
            ),
        ),
        JobListItem(
            id="job-2",
            title="Python Dev",
            company="Startup",
            location="Remote",
            source="naukri",
            application_url="https://example.com/job2",
            required_skills=["Python", "Docker", "Redis"],
            match=MatchBreakdown(
                overall_score=75.0,
                skill_score=70.0,
                matched_skills=["Python"],
                missing_skills=["Docker", "Redis"],
                recommendation="GOOD_MATCH"
            ),
        ),
    ]

    mock_new = [mock_scored[0]]

    with patch("app.services.dashboard_service.search_jobs_db", side_effect=[mock_scored, mock_new]), \
         patch("app.services.dashboard_service.get_source_registry") as mock_registry, \
         patch("app.services.dashboard_service.get_recent_sync_logs", return_value=[{
             "timestamp": datetime.now(timezone.utc),
             "status": "completed",
             "duration_seconds": 12.5,
             "jobs_discovered": 1284,
             "jobs_added": 85,
         }]):

        reg_instance = MagicMock()
        reg_instance.health_check_all = AsyncMock(return_value={"linkedin": True, "naukri": True})
        mock_src = MagicMock()
        mock_src.enabled = True
        mock_src.status = "ok"
        mock_src.get_metrics.return_value = MagicMock(model_dump=lambda: {})
        reg_instance._sources = {"linkedin": mock_src, "naukri": mock_src}
        mock_registry.return_value = reg_instance

        resp = await get_dashboard_data(mock_db, user_id, profile, pref)

        assert resp.greeting in ["Good morning", "Good afternoon", "Good evening", "Good night"]
        # Funnel
        assert resp.funnel.fresh_jobs_count == 1284
        assert resp.funnel.strong_matches_count == 2
        assert resp.funnel.excellent_matches_count == 1
        # Application summary
        assert resp.application_summary.total_tracked == 15
        assert resp.application_summary.saved == 10
        assert resp.application_summary.applied == 4
        assert resp.application_summary.interviewing == 1
        # Skill gaps
        gap_skills = [g.skill for g in resp.skill_gaps]
        assert "Docker" in gap_skills
        assert "Python" not in gap_skills  # Candidate already has Python
        # Source health
        assert resp.source_health.healthy_count == 2
        assert resp.source_health.status == "ok"
        # Sync status
        assert resp.sync_status.jobs_discovered == 1284
