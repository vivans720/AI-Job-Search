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
