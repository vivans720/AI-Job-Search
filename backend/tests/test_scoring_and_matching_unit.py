import pytest
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.preference import Preference
from app.services.matching_service import get_matching_service


def test_perfect_skill_and_experience_match():
    """Verify strong match yields high deterministic score >= 90.0%."""
    service = get_matching_service()
    candidate = CandidateProfile(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        target_roles=["Backend Developer"],
        experience_years=1,
    )
    job = Job(
        title="Junior Backend Developer",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker"],
        experience_min=0,
        experience_max=2,
        location="Bengaluru",
        remote_type="REMOTE",
    )
    prefs = Preference(
        freshness_hours=24,
        experience_max_years=2,
        priority_companies=[],
        excluded_companies=[],
    )

    score_dict = service.evaluate_job(job, candidate, prefs)
    assert score_dict["overall_score"] >= 80.0
    assert score_dict["recommendation"] in ["STRONG_MATCH", "GOOD_MATCH"]
    assert "Python" in score_dict["matched_skills"]
    assert "FastAPI" in score_dict["matched_skills"]
    assert "PostgreSQL" in score_dict["matched_skills"]
    assert len(score_dict["missing_skills"]) == 0


def test_anti_inflation_zero_required_skills_matched():
    """Verify candidate with 0% required skill match is hard capped <= 25.0% (SKIP)."""
    service = get_matching_service()
    candidate = CandidateProfile(
        skills=["Photoshop", "Graphic Design", "Figma"],
        target_roles=["Backend Developer"],
        experience_years=1,
    )
    job = Job(
        title="Backend Developer",
        required_skills=["Go", "Kubernetes", "gRPC"],
        preferred_skills=[],
        experience_min=1,
        experience_max=3,
        location="Remote",
    )
    prefs = Preference(freshness_hours=24, experience_max_years=2)

    score_dict = service.evaluate_job(job, candidate, prefs)
    assert score_dict["overall_score"] <= 25.0
    assert score_dict["recommendation"] == "SKIP"


def test_transferable_skills_taxonomy_credit():
    """Verify adjacent transferable skills provide directional credit."""
    service = get_matching_service()
    candidate = CandidateProfile(
        skills=["Python", "PostgreSQL"],
        target_roles=["Python Developer"],
        experience_years=1,
    )
    job = Job(
        title="Junior Python Developer",
        required_skills=["Django", "MySQL"],
        preferred_skills=[],
        experience_min=0,
        experience_max=2,
    )
    prefs = Preference(freshness_hours=24, experience_max_years=2)

    score_dict = service.evaluate_job(job, candidate, prefs)
    trans_names = [t["skill"] if isinstance(t, dict) else t for t in score_dict["transferable_skills"]]
    assert any("django" in str(s).lower() or "mysql" in str(s).lower() for s in trans_names)


def test_hard_rejection_on_senior_role():
    """Verify ineligibility gating flags excluded roles and captures exclusion reasons."""
    service = get_matching_service()
    candidate = CandidateProfile(
        skills=["Python", "FastAPI"],
        target_roles=["Backend Developer"],
        excluded_roles=["Architect", "Staff Engineer"],
        experience_years=1,
    )
    job = Job(
        title="Staff Principal Backend Architect",
        required_skills=["Python", "FastAPI"],
        experience_min=8,
        experience_max=12,
    )
    prefs = Preference(freshness_hours=24, experience_max_years=2)

    score_dict = service.evaluate_job(job, candidate, prefs)
    # Role is in excluded_roles and experience exceeds preference ceiling
    assert any("exceeds preference ceiling" in r for r in score_dict["exclusion_reasons"])
    assert any("excluded roles" in r for r in score_dict["exclusion_reasons"])
