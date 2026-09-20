import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import select

# Add mcp-server directory
mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from app.database import async_session_factory
from app.models.job import Job
from app.models.notification import DailyDigest, DigestNotifiedJob
from app.models.user import User
from app.services.scheduled_search_service import ScheduledSearchService
from app.services.user_service import get_or_create_default_user


@pytest.mark.asyncio
async def test_daily_digest_model_and_dedupe():
    """Verify DailyDigest persistence and DigestNotifiedJob unique constraints."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)

        # Ensure a fresh unique job exists in jobs table for dedupe test
        unique_hash = f"testhash_{uuid.uuid4().hex[:12]}"
        job = Job(
            title="Software Engineer",
            company_name="Acme Tech",
            description="Python developer",
            source="linkedin",
            source_url="https://example.com/job",
            application_url="https://example.com/apply",
            job_hash=unique_hash,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # 1. Create Daily Digest
        digest = DailyDigest(
            user_id=user.id,
            digest_date=datetime.now(timezone.utc),
            summary="# Morning Briefing Test\nFound fresh opportunities.",
            job_ids=[str(job.id)],
            total_found=10,
            strong_matches_count=1,
            status="DELIVERED",
        )
        db.add(digest)
        await db.commit()
        await db.refresh(digest)
        assert digest.id is not None
        assert digest.status == "DELIVERED"

        # 2. Test Deduplication on DigestNotifiedJob
        notified_1 = DigestNotifiedJob(
            user_id=user.id,
            job_id=job.id,
            digest_id=digest.id,
            notified_at=datetime.now(timezone.utc),
        )
        db.add(notified_1)
        await db.commit()

        # Duplicate notification for same user and job should raise IntegrityError
        notified_2 = DigestNotifiedJob(
            user_id=user.id,
            job_id=job.id,
            digest_id=digest.id,
            notified_at=datetime.now(timezone.utc),
        )
        db.add(notified_2)
        with pytest.raises(Exception):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_scheduled_search_service_execution():
    """Verify scheduled job search runner handles execution and zero-match cases cleanly."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)

        # Run with threshold 99% to test graceful zero-match handling
        res_zero = await ScheduledSearchService.run_scheduled_job_search(
            db=db,
            user_id=user.id,
            freshness_hours=24,
            match_threshold_override=99,
            dry_run=False,
        )
        assert res_zero["status"] in ("NO_MATCHES", "DELIVERED")
        assert "Daily Tech Job Digest" in res_zero["summary"]
        assert res_zero["digest_id"] is not None

        # Verify digest was saved and can be retrieved
        latest = await ScheduledSearchService.get_latest_digest(db, user.id)
        assert latest is not None
        assert latest.id == uuid.UUID(res_zero["digest_id"])

        # Test dry-run execution does not mutate DB
        res_dry = await ScheduledSearchService.run_scheduled_job_search(
            db=db,
            user_id=user.id,
            freshness_hours=24,
            match_threshold_override=50,
            dry_run=True,
        )
        assert res_dry["dry_run"] is True
        assert res_dry["digest_id"] is None


@pytest.mark.asyncio
async def test_mcp_digest_tools():
    """Verify MCP tools for daily digests work via server interface."""
    from server import server

    # 1. Test get_daily_digests
    res = await server.call_tool("get_daily_digests", {"limit": 5})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "ok"
    assert "digests" in data
    assert "digests_count" in data

    # 2. Test create_daily_digest
    create_res = await server.call_tool(
        "create_daily_digest",
        {
            "summary": "# Test Digest from MCP\nTop jobs found.",
            "job_ids": [],
            "status": "DELIVERED",
        },
    )
    assert not create_res.is_error
    create_data = json.loads(create_res.content[0].text)
    assert create_data["status"] == "ok"
    assert "digest_id" in create_data


@pytest.mark.asyncio
async def test_api_digests_endpoints(async_client):
    """Verify REST endpoints for daily digests."""
    # List digests under /api/v1/digests
    list_res = await async_client.get("/api/v1/digests")
    assert list_res.status_code == 200
    digests = list_res.json()
    assert isinstance(digests, list)
    assert len(digests) >= 1

    # Get latest digest
    latest_res = await async_client.get("/api/v1/digests/latest")
    assert latest_res.status_code == 200
    latest = latest_res.json()
    assert "summary" in latest
    assert "digest_date" in latest

    # Trigger scheduled job search via endpoint
    trigger_res = await async_client.post(
        "/api/v1/digests/run-scheduled-search",
        json={"freshness_hours": 24, "dry_run": True},
    )
    assert trigger_res.status_code == 200
    trig_data = trigger_res.json()
    assert trig_data["dry_run"] is True
    assert "summary" in trig_data
