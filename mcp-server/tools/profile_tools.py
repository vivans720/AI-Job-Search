import sys
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.preference_service import get_or_create_preferences
from app.services.profile_service import get_candidate_profile
from app.services.user_service import get_or_create_default_user


async def handle_get_candidate_profile() -> dict[str, Any]:
    """
    Returns structured information about the candidate extracted from their resume
    and configured via profile preferences.
    """
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        profile = await get_candidate_profile(db, user.id)
        prefs = await get_or_create_preferences(db, user.id)

        if not profile:
            return {
                "status": "not_found",
                "message": "Candidate profile not found. Please upload a resume first.",
                "target_roles": [
                    "Full Stack Developer",
                    "Backend Developer",
                    "Frontend Developer",
                    "AI Engineer",
                    "Software Engineer",
                ],
                "experience_level": "FRESHER",
                "experience_years": 0,
                "skills": [],
                "programming_languages": [],
                "frameworks": [],
                "databases": [],
                "cloud": [],
                "preferred_locations": ["Bengaluru", "Remote"],
                "remote_preference": True,
                "internship_allowed": True,
                "minimum_salary_lpa": None,
                "freshness_hours": prefs.freshness_hours,
            }

        return {
            "status": "ok",
            "candidate_id": str(user.id),
            "target_roles": profile.target_roles,
            "excluded_roles": profile.excluded_roles,
            "experience_level": profile.experience_level,
            "experience_years": profile.experience_years,
            "skills": profile.skills,
            "programming_languages": profile.programming_languages,
            "frameworks": profile.frameworks,
            "databases": profile.databases,
            "cloud": profile.cloud,
            "tools": profile.tools,
            "preferred_locations": profile.preferred_locations,
            "remote_preference": profile.remote_preference,
            "internship_allowed": profile.internship_allowed,
            "fulltime_allowed": profile.fulltime_allowed,
            "minimum_salary_lpa": profile.minimum_salary_lpa,
            "freshness_hours": prefs.freshness_hours,
            "experience_max_years": prefs.experience_max_years,
            "match_threshold": prefs.match_threshold,
            "projects_count": len(profile.projects or []),
            "education": profile.education,
        }


async def handle_get_preferences() -> dict[str, Any]:
    """Returns candidate search and synchronization preferences."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        prefs = await get_or_create_preferences(db, user.id)
        return {
            "status": "ok",
            "user_id": str(user.id),
            "freshness_hours": prefs.freshness_hours,
            "experience_max_years": prefs.experience_max_years,
            "experience_level": prefs.experience_level,
            "preferred_locations": prefs.preferred_locations or [],
            "role_type": prefs.role_type,
            "source_boards": prefs.source_boards or [],
            "preferred_technologies": prefs.preferred_technologies or [],
            "preferred_industries": prefs.preferred_industries or [],
            "priority_companies": prefs.priority_companies or [],
            "excluded_companies": prefs.excluded_companies or [],
            "match_threshold": prefs.match_threshold,
            "auto_sync_enabled": prefs.auto_sync_enabled,
            "sync_interval_hours": prefs.sync_interval_hours,
        }


async def handle_update_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    """Updates candidate search preferences safely with validation."""
    from app.schemas.preference import PreferenceUpdate
    from app.services.preference_service import update_preferences

    # Whitelist allowed keys for agent preference update
    allowed_keys = {
        "freshness_hours",
        "experience_max_years",
        "experience_level",
        "match_threshold",
        "preferred_locations",
        "role_type",
        "source_boards",
        "preferred_technologies",
        "preferred_industries",
        "priority_companies",
        "excluded_companies",
        "sync_interval_hours",
        "auto_sync_enabled",
    }
    filtered_updates = {k: v for k, v in updates.items() if k in allowed_keys}
    if not filtered_updates:
        return {"error": "No valid preference update fields provided."}

    try:
        pref_in = PreferenceUpdate(**filtered_updates)
    except Exception as e:
        return {"error": f"Validation error: {str(e)}"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        updated_pref = await update_preferences(db, user.id, pref_in)
        return {
            "status": "ok",
            "message": "Preferences updated successfully",
            "preferences": {
                "freshness_hours": updated_pref.freshness_hours,
                "experience_max_years": updated_pref.experience_max_years,
                "experience_level": updated_pref.experience_level,
                "preferred_locations": updated_pref.preferred_locations or [],
                "role_type": updated_pref.role_type,
                "source_boards": updated_pref.source_boards or [],
                "preferred_technologies": updated_pref.preferred_technologies or [],
                "match_threshold": updated_pref.match_threshold,
                "auto_sync_enabled": updated_pref.auto_sync_enabled,
            },
        }

