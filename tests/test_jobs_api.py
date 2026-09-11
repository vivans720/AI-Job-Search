import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_search_jobs_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/jobs?freshness_hours=24&limit=10")
        assert res.status_code == 200
        jobs = res.json()
        assert isinstance(jobs, list)
        assert len(jobs) > 0

        first = jobs[0]
        assert "id" in first
        assert "title" in first
        assert "company" in first
        assert "application_url" in first
        assert "match" in first
        if first["match"]:
            assert "overall_score" in first["match"]
            assert "recommendation" in first["match"]


@pytest.mark.asyncio
async def test_get_job_detail_and_match_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        list_res = await ac.get("/api/v1/jobs?limit=1")
        assert list_res.status_code == 200
        jobs = list_res.json()
        assert len(jobs) > 0
        job_id = jobs[0]["id"]

        # 1. Detail endpoint
        detail_res = await ac.get(f"/api/v1/jobs/{job_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == job_id
        assert "description" in detail
        assert "match" in detail

        # 2. Match calculation endpoint
        match_res = await ac.post(f"/api/v1/jobs/{job_id}/match")
        assert match_res.status_code == 200
        match_data = match_res.json()
        assert "overall_score" in match_data
        assert "recommendation" in match_data
        assert "matched_skills" in match_data


@pytest.mark.asyncio
async def test_rank_jobs_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        list_res = await ac.get("/api/v1/jobs?limit=3")
        jobs = list_res.json()
        job_ids = [j["id"] for j in jobs]

        rank_res = await ac.post("/api/v1/jobs/rank", json={"job_ids": job_ids})
        assert rank_res.status_code == 200
        ranked = rank_res.json()["ranked_jobs"]
        assert len(ranked) == len(job_ids)
        # Ensure descending sort
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_job_status_tracking_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        list_res = await ac.get("/api/v1/jobs?limit=1")
        job_id = list_res.json()[0]["id"]

        # Save job
        save_res = await ac.post(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "SAVED", "notes": "Interested in FastAPI backend stack"},
        )
        assert save_res.status_code == 200
        saved = save_res.json()
        assert saved["status"] == "SAVED"
        assert saved["notes"] == "Interested in FastAPI backend stack"

        # Verify listed in /jobs/saved
        saved_list_res = await ac.get("/api/v1/jobs/saved?status=SAVED")
        assert saved_list_res.status_code == 200
        items = saved_list_res.json()
        assert any(it["job_id"] == job_id for it in items)

        # Update to APPLIED
        applied_res = await ac.post(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "APPLIED", "notes": "Applied via careers portal on 2026-09-04"},
        )
        assert applied_res.status_code == 200
        assert applied_res.json()["status"] == "APPLIED"

        # Cleanup: reset status back to DISCOVERED
        await ac.post(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "DISCOVERED"},
        )


@pytest.mark.asyncio
async def test_dashboard_stats_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/dashboard/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_fresh_jobs" in data
        assert "strong_matches" in data
        assert "pipeline" in data
        assert "timezone" in data
        assert data["timezone"] == "Asia/Kolkata"
        assert isinstance(data["pipeline"], dict)
        assert "candidate" in data


@pytest.mark.asyncio
async def test_agent_briefing_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/agent/briefing")
        assert res.status_code == 200
        data = res.json()
        assert "briefing" in data
        assert "top_matches" in data
        assert isinstance(data["top_matches"], list)


@pytest.mark.asyncio
async def test_jobs_sync_api_internshala():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/jobs/sync?source=internshala")
        assert res.status_code == 200
        data = res.json()
        assert "total_discovered" in data
        assert "fresh_jobs" in data


@pytest.mark.asyncio
async def test_save_and_reject_exclusion_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch initial fresh jobs
        res = await ac.get("/api/v1/jobs?limit=10")
        assert res.status_code == 200
        jobs = res.json()
        assert len(jobs) >= 2

        target_job_id = jobs[0]["id"]
        saved_target_id = jobs[1]["id"]

        # 2. Reject first job
        reject_res = await ac.post(
            f"/api/v1/jobs/{target_job_id}/status",
            json={"status": "REJECTED"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

        # 3. Verify rejected job is now excluded from discovery
        res_after_reject = await ac.get("/api/v1/jobs?limit=20")
        assert res_after_reject.status_code == 200
        jobs_after = res_after_reject.json()
        assert not any(j["id"] == target_job_id for j in jobs_after)

        # 4. Save second job and verify it is excluded from discovery and moved to /jobs/saved
        save_res = await ac.post(
            f"/api/v1/jobs/{saved_target_id}/status",
            json={"status": "SAVED"},
        )
        assert save_res.status_code == 200
        assert save_res.json()["status"] == "SAVED"

        # Verify saved job is now excluded from discovery feed
        res_after_save = await ac.get("/api/v1/jobs?limit=20")
        assert res_after_save.status_code == 200
        jobs_saved_check = res_after_save.json()
        assert not any(j["id"] == saved_target_id for j in jobs_saved_check)

        # Verify saved job is accessible in saved jobs endpoint
        saved_list_res = await ac.get("/api/v1/jobs/saved?status=SAVED")
        assert saved_list_res.status_code == 200
        saved_items = saved_list_res.json()
        assert any(it["job_id"] == saved_target_id for it in saved_items)

        # 5. Undo both rejection and save by setting back to DISCOVERED, verify they reappear
        undo_res = await ac.post(
            f"/api/v1/jobs/{target_job_id}/status",
            json={"status": "DISCOVERED"},
        )
        assert undo_res.status_code == 200

        undo_save_res = await ac.post(
            f"/api/v1/jobs/{saved_target_id}/status",
            json={"status": "DISCOVERED"},
        )
        assert undo_save_res.status_code == 200

        res_after_undo = await ac.get("/api/v1/jobs?limit=20")
        assert res_after_undo.status_code == 200
        jobs_final = res_after_undo.json()
        assert any(j["id"] == target_job_id for j in jobs_final)
        assert any(j["id"] == saved_target_id for j in jobs_final)


@pytest.mark.asyncio
async def test_search_jobs_api_pagination():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/jobs?page=1&page_size=5")
        assert res.status_code == 200
        assert "x-total-count" in res.headers or "X-Total-Count" in res.headers
        assert "x-page" in res.headers or "X-Page" in res.headers
        assert "x-page-size" in res.headers or "X-Page-Size" in res.headers
        assert "x-total-pages" in res.headers or "X-Total-Pages" in res.headers
        total_header = res.headers.get("X-Total-Count") or res.headers.get("x-total-count")
        assert total_header is not None
        assert int(total_header) >= 0
        jobs = res.json()
        assert isinstance(jobs, list)
        assert len(jobs) <= 5


@pytest.mark.asyncio
async def test_search_jobs_api_experience_filter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test fresher filter (experience_max=0)
        res_fresher = await ac.get("/api/v1/jobs?experience_max=0&limit=10")
        assert res_fresher.status_code == 200
        jobs_fresher = res_fresher.json()
        assert isinstance(jobs_fresher, list)
        for j in jobs_fresher:
            # Must not be senior (> 0 min exp unless internship or unspecified)
            if j.get("employment_type") != "INTERNSHIP" and j.get("experience_min") is not None:
                assert j["experience_min"] == 0

        # Test range filter (experience_min=1, experience_max=2)
        res_range = await ac.get("/api/v1/jobs?experience_min=1&experience_max=2&limit=10")
        assert res_range.status_code == 200
        jobs_range = res_range.json()
        assert isinstance(jobs_range, list)
        for j in jobs_range:
            if j.get("experience_min") is not None:
                assert j["experience_min"] <= 2


@pytest.mark.asyncio
async def test_trigger_job_sync_async_and_status():
    from unittest.mock import AsyncMock, patch

    mock_queue = AsyncMock()
    mock_queue.enqueue.return_value = "job-phase36-test"
    mock_queue.get_job_status.return_value = {
        "job_id": "job-phase36-test",
        "status": "completed",
        "task_type": "sync_source",
        "result": {"canonical_saved": 4, "total_discovered": 10},
    }

    with patch("app.services.queue_service.task_queue.enqueue", mock_queue.enqueue), \
         patch("app.services.queue_service.task_queue.get_job_status", mock_queue.get_job_status):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Enqueue job (202 Accepted)
            res = await ac.post("/api/v1/jobs/sync?source=internshala&async_mode=true")
            assert res.status_code == 202
            data = res.json()
            assert data["job_id"] == "job-phase36-test"
            assert data["status"] == "queued"

            # 2. Check status (200 OK)
            status_res = await ac.get("/api/v1/jobs/sync/status/job-phase36-test")
            assert status_res.status_code == 200
            status_data = status_res.json()
            assert status_data["status"] == "completed"
            assert status_data["result"]["canonical_saved"] == 4



