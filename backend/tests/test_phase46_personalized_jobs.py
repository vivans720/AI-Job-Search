import pytest
from app.models.job import Job
from app.models.candidate_profile import CandidateProfile
from app.models.preference import Preference
from app.services.matching_service import MatchingService

def test_phase46_for_you_filter_logic():
    """Verify personalized matching logic and ranking criteria for Phase 46."""
    matching_svc = MatchingService()
    
    # Candidate profile with Python / FastAPI
    profile = CandidateProfile(
        experience_level="FRESHER",
        experience_years=2,
        target_roles=["Backend Engineer", "Full Stack Engineer"],
        skills=["python", "fastapi", "postgresql", "docker"],
    )
    
    prefs = Preference(
        preferred_technologies=["python", "fastapi"],
        freshness_hours=24,
        experience_max_years=3,
        match_threshold=40,
    )
    
    # Job 1: High fit
    job_high = Job(
        title="Backend Engineer - Python",
        company_name="Alpha Tech",
        location="Bengaluru",
        remote_type="REMOTE",
        required_skills=["python", "fastapi"],
        preferred_skills=["docker"],
        experience_min=1,
        experience_max=3,
        description="Great backend role using Python and FastAPI."
    )
    
    # Job 2: Low fit / Mismatch
    job_low = Job(
        title="Java Enterprise Developer",
        company_name="Legacy Systems",
        location="Chennai",
        remote_type="ONSITE",
        required_skills=["java", "spring boot", "oracle"],
        preferred_skills=["angular"],
        experience_min=5,
        experience_max=8,
        description="Enterprise Java developer with 5+ years experience."
    )
    
    eval_high = matching_svc.evaluate_job(job_high, profile, prefs)
    eval_low = matching_svc.evaluate_job(job_low, profile, prefs)
    
    # Verify high fit passes Phase 46 'For You' threshold (>= 40.0)
    assert eval_high["overall_score"] >= 40.0
    assert eval_high["recommendation"] in ["STRONG_MATCH", "GOOD_MATCH", "CONSIDER"]
    
    # Verify low fit fails 'For You' threshold or scores low
    assert eval_low["overall_score"] < 40.0
    assert eval_low["recommendation"] in ["LOW_PRIORITY", "SKIP"]

    # Verify ranking logic puts high fit first
    jobs_ranked = sorted([eval_low, eval_high], key=lambda x: x["overall_score"], reverse=True)
    assert jobs_ranked[0] == eval_high
    assert jobs_ranked[1] == eval_low
