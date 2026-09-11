import pytest
from app.schemas.preference import SetupStatusResponse, PreferenceUpdate
from app.models.preference import Preference
import uuid

def test_setup_status_schema():
    uid = uuid.uuid4()
    resp = SetupStatusResponse(
        setup_completed=False,
        has_profile=True,
        has_resume=False,
        has_ai_provider=True,
        has_sources=True,
        user_id=uid,
        profile_summary={"experience_level": "junior", "experience_years": 1, "target_roles": ["Backend"], "skills_count": 5}
    )
    assert resp.setup_completed is False
    assert resp.has_profile is True
    assert resp.user_id == uid
    assert resp.profile_summary["skills_count"] == 5

def test_preference_update_setup_completed():
    update = PreferenceUpdate(setup_completed=True)
    assert update.setup_completed is True
    dump = update.model_dump(exclude_unset=True)
    assert dump == {"setup_completed": True}
