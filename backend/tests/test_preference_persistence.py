import uuid
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.database import get_db
from app.models.preference import Preference
from app.models.user import User
from app.schemas.preference import (
    PreferenceUpdate,
    PreferenceResponse,
    ALLOWED_FRESHNESS,
    ALLOWED_EXPERIENCE,
    ALLOWED_ROLE_TYPES,
    ALLOWED_SOURCE_BOARDS,
)
from app.services.preference_service import update_preferences


# ==============================================================================
# 1. Pydantic Schema Validation Tests for All 7 Fields
# ==============================================================================

def test_freshness_hours_validation():
    """Verify discrete freshness hours validation (1, 4, 8, 12, 16, 24)."""
    for valid_h in ALLOWED_FRESHNESS:
        update = PreferenceUpdate(freshness_hours=valid_h)
        assert update.freshness_hours == valid_h

    # Invalid freshness values outside the 6 discrete options
    for invalid_h in [0, 2, 5, 7, 25, 48, 168, -1]:
        with pytest.raises(ValidationError):
            PreferenceUpdate(freshness_hours=invalid_h)


def test_experience_level_validation():
    """Verify experience level tier options validation."""
    for valid_tier in ALLOWED_EXPERIENCE:
        update = PreferenceUpdate(experience_level=valid_tier)
        assert update.experience_level == valid_tier

    # Case insensitive normalization
    assert PreferenceUpdate(experience_level="fresher").experience_level == "FRESHER"
    assert PreferenceUpdate(experience_level="3_plus").experience_level == "3_PLUS"

    # Invalid experience tiers
    for invalid_exp in ["SENIOR", "MID", "10_YEARS", "EXPERT"]:
        with pytest.raises(ValidationError):
            PreferenceUpdate(experience_level=invalid_exp)


def test_match_threshold_validation():
    """Verify minimum match threshold validation (0 - 100%)."""
    for valid_thresh in [0, 1, 50, 75, 99, 100]:
        update = PreferenceUpdate(match_threshold=valid_thresh)
        assert update.match_threshold == valid_thresh

    for invalid_thresh in [-1, -50, 101, 200]:
        with pytest.raises(ValidationError):
            PreferenceUpdate(match_threshold=invalid_thresh)


def test_role_type_validation():
    """Verify role type validation (ALL, JOBS, INTERNSHIPS)."""
    for valid_role in ALLOWED_ROLE_TYPES:
        update = PreferenceUpdate(role_type=valid_role)
        assert update.role_type == valid_role

    # Case insensitive normalization
    assert PreferenceUpdate(role_type="jobs").role_type == "JOBS"
    assert PreferenceUpdate(role_type="internships").role_type == "INTERNSHIPS"

    for invalid_role in ["FREELANCE", "CONTRACT", "TEMPORARY", "PART_TIME"]:
        with pytest.raises(ValidationError):
            PreferenceUpdate(role_type=invalid_role)


def test_source_boards_validation():
    """Verify source job boards validation (LINKEDIN, NAUKRI, INTERNSHALA, INDEED)."""
    valid_boards = ["LINKEDIN", "NAUKRI", "INTERNSHALA", "INDEED"]
    update = PreferenceUpdate(source_boards=valid_boards)
    assert update.source_boards == valid_boards

    # Case insensitive
    update_lower = PreferenceUpdate(source_boards=["linkedin", "naukri"])
    assert update_lower.source_boards == ["LINKEDIN", "NAUKRI"]

    with pytest.raises(ValidationError):
        PreferenceUpdate(source_boards=["LINKEDIN", "UNKNOWN_BOARD"])


def test_preferred_locations_and_excluded_companies_validation():
    """Verify preferred locations and excluded companies array validation."""
    locs = ["Bengaluru", "Pune", "Remote", "Hyderabad"]
    excluded = ["Revature", "Wipro", "TCS"]
    update = PreferenceUpdate(
        preferred_locations=locs,
        excluded_companies=excluded,
    )
    assert update.preferred_locations == locs
    assert update.excluded_companies == excluded


# ==============================================================================
# 2. Serialization & Deserialization Tests
# ==============================================================================

def test_preference_update_serialization_roundtrip():
    """Verify PreferenceUpdate serializes to dict and deserializes cleanly."""
    original = PreferenceUpdate(
        freshness_hours=12,
        experience_level="1_2",
        match_threshold=70,
        preferred_locations=["Bengaluru", "Remote"],
        role_type="JOBS",
        source_boards=["LINKEDIN", "NAUKRI"],
        excluded_companies=["SpamAgency"],
        priority_companies=["Google"],
    )
    dumped = original.model_dump(exclude_unset=True)
    assert dumped["freshness_hours"] == 12
    assert dumped["experience_level"] == "1_2"
    assert dumped["match_threshold"] == 70
    assert dumped["role_type"] == "JOBS"
    assert dumped["source_boards"] == ["LINKEDIN", "NAUKRI"]

    restored = PreferenceUpdate.model_validate(dumped)
    assert restored.freshness_hours == original.freshness_hours
    assert restored.experience_level == original.experience_level
    assert restored.match_threshold == original.match_threshold
    assert restored.preferred_locations == original.preferred_locations
    assert restored.role_type == original.role_type
    assert restored.source_boards == original.source_boards
    assert restored.excluded_companies == original.excluded_companies


def test_preference_response_serialization():
    """Verify PreferenceResponse serialization with all 7 fields."""
    uid = uuid.uuid4()
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    resp = PreferenceResponse(
        id=pid,
        user_id=uid,
        freshness_hours=8,
        experience_max_years=2,
        experience_level="FRESHER",
        match_threshold=80,
        preferred_locations=["Delhi NCR", "Remote"],
        role_type="INTERNSHIPS",
        source_boards=["INTERNSHALA", "LINKEDIN"],
        preferred_technologies=["Python", "FastAPI"],
        preferred_industries=["Fintech"],
        priority_companies=["Stripe"],
        excluded_companies=["ConsultancyX"],
        updated_at=now,
    )

    data = resp.model_dump()
    assert data["id"] == pid
    assert data["user_id"] == uid
    assert data["freshness_hours"] == 8
    assert data["experience_level"] == "FRESHER"
    assert data["match_threshold"] == 80
    assert data["preferred_locations"] == ["Delhi NCR", "Remote"]
    assert data["role_type"] == "INTERNSHIPS"
    assert data["source_boards"] == ["INTERNSHALA", "LINKEDIN"]
    assert data["excluded_companies"] == ["ConsultancyX"]


# ==============================================================================
# 3. Model Column Defaults & Preference Service Updates
# ==============================================================================

def test_preference_model_defaults():
    """Verify Preference model initializes with default search criteria."""
    pref = Preference(user_id=uuid.uuid4())
    assert pref.freshness_hours == 24
    assert pref.match_threshold == 60
    assert pref.experience_level == "ALL"
    assert pref.role_type == "ALL"
    assert pref.preferred_locations == []
    # source_boards default callable or list
    boards = pref.source_boards() if callable(pref.source_boards) else pref.source_boards
    assert "LINKEDIN" in boards
    assert "NAUKRI" in boards


@pytest.mark.asyncio
async def test_update_preferences_service_all_7_fields():
    """Verify update_preferences service updates all 7 search criteria fields."""
    user_id = uuid.uuid4()
    mock_db = AsyncMock()

    existing_pref = Preference(
        id=uuid.uuid4(),
        user_id=user_id,
        freshness_hours=24,
        experience_level="ALL",
        match_threshold=60,
        preferred_locations=["Remote"],
        role_type="ALL",
        source_boards=["LINKEDIN"],
        excluded_companies=[],
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_pref
    mock_db.execute.return_value = mock_result

    updates = PreferenceUpdate(
        freshness_hours=4,
        experience_level="0_1",
        match_threshold=85,
        preferred_locations=["Bengaluru", "Pune", "Remote"],
        role_type="JOBS",
        source_boards=["LINKEDIN", "NAUKRI", "INDEED"],
        excluded_companies=["Revature", "TechStaffing"],
    )

    updated_pref = await update_preferences(mock_db, user_id, updates)

    assert updated_pref.freshness_hours == 4
    assert updated_pref.experience_level == "0_1"
    assert updated_pref.match_threshold == 85
    assert updated_pref.preferred_locations == ["Bengaluru", "Pune", "Remote"]
    assert updated_pref.role_type == "JOBS"
    assert updated_pref.source_boards == ["LINKEDIN", "NAUKRI", "INDEED"]
    assert updated_pref.excluded_companies == ["Revature", "TechStaffing"]
    assert mock_db.commit.called


# ==============================================================================
# 4. API Endpoints for Preferences (GET and PUT)
# ==============================================================================

@pytest.mark.asyncio
async def test_api_get_preferences_returns_all_7_fields():
    """Verify GET /api/v1/preferences returns all 7 search preference fields."""
    user_id = uuid.uuid4()
    mock_user = User(id=user_id, email="dev@example.com")

    mock_pref = Preference(
        id=uuid.uuid4(),
        user_id=user_id,
        freshness_hours=16,
        experience_level="2_3",
        match_threshold=70,
        preferred_locations=["Hyderabad", "Remote"],
        role_type="JOBS",
        source_boards=["LINKEDIN", "NAUKRI"],
        excluded_companies=["ConsultingCo"],
        priority_companies=["Google"],
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()

    # Provide user and pref to get_or_create helpers
    with patch("app.api.v1.preferences.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("app.api.v1.preferences.get_or_create_preferences", new_callable=AsyncMock) as mock_get_pref:
        mock_get_user.return_value = mock_user
        mock_get_pref.return_value = mock_pref

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/v1/preferences")
                assert res.status_code == 200
                data = res.json()

                assert data["freshness_hours"] == 16
                assert data["experience_level"] == "2_3"
                assert data["match_threshold"] == 70
                assert data["preferred_locations"] == ["Hyderabad", "Remote"]
                assert data["role_type"] == "JOBS"
                assert data["source_boards"] == ["LINKEDIN", "NAUKRI"]
                assert data["excluded_companies"] == ["ConsultingCo"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_put_preferences_valid_updates():
    """Verify PUT /api/v1/preferences updates all 7 fields and returns 200."""
    user_id = uuid.uuid4()
    mock_user = User(id=user_id, email="dev@example.com")

    updated_pref = Preference(
        id=uuid.uuid4(),
        user_id=user_id,
        freshness_hours=1,
        experience_level="FRESHER",
        match_threshold=90,
        preferred_locations=["Bengaluru"],
        role_type="INTERNSHIPS",
        source_boards=["INTERNSHALA"],
        excluded_companies=["BadCompany"],
        priority_companies=["Razorpay"],
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()

    with patch("app.api.v1.preferences.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("app.api.v1.preferences.update_preferences", new_callable=AsyncMock) as mock_update_pref:
        mock_get_user.return_value = mock_user
        mock_update_pref.return_value = updated_pref

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {
                    "freshness_hours": 1,
                    "experience_level": "FRESHER",
                    "match_threshold": 90,
                    "preferred_locations": ["Bengaluru"],
                    "role_type": "INTERNSHIPS",
                    "source_boards": ["INTERNSHALA"],
                    "excluded_companies": ["BadCompany"],
                }
                res = await client.put("/api/v1/preferences", json=payload)
                assert res.status_code == 200
                data = res.json()

                assert data["freshness_hours"] == 1
                assert data["experience_level"] == "FRESHER"
                assert data["match_threshold"] == 90
                assert data["preferred_locations"] == ["Bengaluru"]
                assert data["role_type"] == "INTERNSHIPS"
                assert data["source_boards"] == ["INTERNSHALA"]
                assert data["excluded_companies"] == ["BadCompany"]
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_put_preferences_invalid_payload_rejected():
    """Verify PUT /api/v1/preferences returns 422 for invalid criteria."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Invalid freshness
            res = await client.put("/api/v1/preferences", json={"freshness_hours": 99})
            assert res.status_code == 422

            # 2. Invalid match threshold
            res = await client.put("/api/v1/preferences", json={"match_threshold": 150})
            assert res.status_code == 422

            # 3. Invalid experience level
            res = await client.put("/api/v1/preferences", json={"experience_level": "UNKNOWN_LEVEL"})
            assert res.status_code == 422

            # 4. Invalid role type
            res = await client.put("/api/v1/preferences", json={"role_type": "INVALID_ROLE"})
            assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()
