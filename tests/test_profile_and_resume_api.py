import pytest
import httpx
from app.intelligence.embedding_provider import get_embedding_provider


@pytest.mark.asyncio
async def test_embedding_provider_shape():
    provider = get_embedding_provider()
    vec = provider.embed("Python Backend Developer FastAPI PostgreSQL")
    assert len(vec) == 384
    assert isinstance(vec[0], float)


@pytest.mark.asyncio
async def test_get_candidate_profile(async_client: httpx.AsyncClient):
    response = await async_client.get("/api/v1/profile")
    assert response.status_code == 200
    data = response.json()
    assert "target_roles" in data
    assert "skills" in data
    assert data["experience_years"] == 0
    assert isinstance(data["target_roles"], list)
    assert len(data["target_roles"]) > 0


@pytest.mark.asyncio
async def test_update_candidate_profile_overrides(async_client: httpx.AsyncClient):
    # Fetch initial state to restore after test
    initial_res = await async_client.get("/api/v1/profile")
    initial_data = initial_res.json() if initial_res.status_code == 200 else {}

    try:
        # Update preferred locations and exclude Data Analyst
        updates = {
            "preferred_locations": ["Bengaluru", "Remote"],
            "excluded_roles": ["Data Analyst", "QA Engineer"],
            "target_roles": ["Backend Developer", "Data Analyst", "AI Engineer"],
        }
        response = await async_client.put("/api/v1/profile", json=updates)
        assert response.status_code == 200
        data = response.json()

        # Data Analyst must be stripped because it is in excluded_roles
        assert "Data Analyst" not in data["target_roles"]
        assert "Backend Developer" in data["target_roles"]
        assert data["manual_overrides"]["target_roles"] is True
        assert data["manual_overrides"]["excluded_roles"] is True
    finally:
        # Restore initial candidate profile so live database is preserved
        if initial_data.get("target_roles"):
            await async_client.put(
                "/api/v1/profile",
                json={
                    "target_roles": initial_data.get("target_roles"),
                    "excluded_roles": initial_data.get("excluded_roles", []),
                    "preferred_locations": initial_data.get("preferred_locations", []),
                },
            )



@pytest.mark.asyncio
async def test_preferences_api(async_client: httpx.AsyncClient):
    # Fetch default preferences
    get_res = await async_client.get("/api/v1/preferences")
    assert get_res.status_code == 200
    pref = get_res.json()
    assert pref["freshness_hours"] in (1, 4, 8, 12, 16, 24)
    assert pref["experience_max_years"] in (0, 1, 2, 3)

    # Update preferences
    put_res = await async_client.put(
        "/api/v1/preferences",
        json={"freshness_hours": 24, "match_threshold": 75, "preferred_technologies": ["Python", "FastAPI"]},
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["match_threshold"] == 75
    assert "FastAPI" in updated["preferred_technologies"]


@pytest.mark.asyncio
async def test_resumes_api(async_client: httpx.AsyncClient):
    response = await async_client.get("/api/v1/resumes")
    assert response.status_code == 200
    resumes = response.json()
    assert isinstance(resumes, list)
    if resumes:
        assert bool(resumes[0]["filename"])
        assert resumes[0]["is_active"] is True
