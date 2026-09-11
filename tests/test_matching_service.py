import pytest

from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.preference import Preference
from app.services.matching_service import MatchingService


def create_mock_profile(
    skills=None,
    target_roles=None,
    excluded_roles=None,
    experience_years=0,
    preferred_locations=None,
    remote_preference=True,
    internship_allowed=True,
) -> CandidateProfile:
    prof = CandidateProfile(
        skills=skills or ["Python", "FastAPI", "React", "Node.js", "PostgreSQL", "JavaScript"],
        target_roles=target_roles or ["Full Stack Developer", "Backend Developer", "AI Engineer"],
        excluded_roles=excluded_roles or ["Data Analyst", "QA Engineer"],
        experience_years=experience_years,
        experience_level="ENTRY_LEVEL" if experience_years <= 1 else "MID_LEVEL",
        preferred_locations=preferred_locations or ["Bengaluru", "Remote"],
        remote_preference=remote_preference,
        internship_allowed=internship_allowed,
        minimum_salary_lpa=8.0,
    )
    return prof


def create_mock_job(
    title="Backend Developer (FastAPI)",
    company_name="Razorpay",
    required_skills=None,
    preferred_skills=None,
    experience_min=0,
    experience_max=1,
    location="Bengaluru",
    remote_type="ONSITE",
    employment_type="FULL_TIME",
    salary_max=1200000.0,
) -> Job:
    job = Job(
        title=title,
        company_name=company_name,
        role_category="BACKEND",
        required_skills=required_skills or ["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=preferred_skills or ["Docker", "Redis"],
        experience_min=experience_min,
        experience_max=experience_max,
        location=location,
        normalized_location=location,
        remote_type=remote_type,
        employment_type=employment_type,
        salary_max=salary_max,
    )
    return job


def test_matching_skill_scores():
    svc = MatchingService()

    # Direct match: all 3 match
    score, direct, missing, transferable = svc.compute_skill_score(
        candidate_skills=["Python", "FastAPI", "PostgreSQL"],
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=[],
    )
    assert score == 100.0
    assert len(direct) == 3
    assert len(missing) == 0

    # Partial / missing match
    score2, direct2, missing2, trans2 = svc.compute_skill_score(
        candidate_skills=["Python"],
        required_skills=["Python", "Go", "Rust"],
        preferred_skills=[],
    )
    assert round(score2) == 33
    assert len(direct2) == 1
    assert len(missing2) == 2


def test_transferable_skills():
    svc = MatchingService()
    # Candidate has Python -> knows Flask/REST APIs transferably
    score, direct, missing, trans = svc.compute_skill_score(
        candidate_skills=["Python"],
        required_skills=["Flask"],
        preferred_skills=[],
    )
    assert score == 50.0  # 50% credit for transferable
    assert len(trans) == 1
    assert "Flask" in trans[0]


def test_experience_fresher_vs_senior():
    svc = MatchingService()

    # Fresher applying to 0-1y role
    score_fresher = svc.compute_experience_score(0, 0, 1, "FULL_TIME", True)
    assert score_fresher == 100.0

    # Fresher applying to Senior 10-15y role
    score_senior = svc.compute_experience_score(0, 10, 15, "FULL_TIME", True)
    assert score_senior == 10.0

    # Nullable experience cases (Recall-First)
    # Both None -> neutral-positive baseline
    assert svc.compute_experience_score(0, None, None, "FULL_TIME", True) == 80.0
    assert svc.compute_experience_score(2, None, None, "FULL_TIME", True) == 80.0

    # min only (e.g. 2+ years)
    assert svc.compute_experience_score(0, 2, None, "FULL_TIME", True) == 70.0
    assert svc.compute_experience_score(3, 2, None, "FULL_TIME", True) == 100.0
    assert svc.compute_experience_score(1, 3, None, "FULL_TIME", True) == 50.0

    # max only (e.g. up to 1 year, up to 2 years)
    assert svc.compute_experience_score(0, None, 1, "FULL_TIME", True) == 100.0
    assert svc.compute_experience_score(0, None, 2, "FULL_TIME", True) == 90.0
    assert svc.compute_experience_score(2, None, 2, "FULL_TIME", True) == 100.0
    assert svc.compute_experience_score(4, None, 2, "FULL_TIME", True) == 80.0


def test_hard_role_exclusion():
    svc = MatchingService()
    profile = create_mock_profile(excluded_roles=["Data Analyst", "QA Engineer"])
    job_qa = create_mock_job(title="QA Automation Engineer")

    res = svc.evaluate_job(job_qa, profile)
    assert res["role_score"] == 0.0
    assert res["is_excluded"] is False


def test_hard_company_exclusion():
    svc = MatchingService()
    profile = create_mock_profile()
    prefs = Preference(excluded_companies=["BannedCorp"])
    job = create_mock_job(company_name="BannedCorp")

    res = svc.evaluate_job(job, profile, prefs)
    assert res["preference_score"] <= 20.0
    assert res["is_excluded"] is False


def test_strong_match_evaluation():
    svc = MatchingService()
    profile = create_mock_profile()
    job = create_mock_job(
        title="Backend Developer (FastAPI)",
        company_name="Razorpay",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        experience_min=0,
        experience_max=1,
        location="Bengaluru",
    )

    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] >= 85.0
    assert res["recommendation"] in ("STRONG_MATCH", "GOOD_MATCH")
    assert res["is_excluded"] is False
    assert len(res["matched_skills"]) == 3


def test_hard_experience_exclusion_high_years():
    svc = MatchingService()
    profile = create_mock_profile(experience_years=0)
    # Job requires 5-8 years experience
    job_senior = create_mock_job(
        title="Backend Developer",
        experience_min=5,
        experience_max=8,
    )

    res = svc.evaluate_job(job_senior, profile)
    assert res["experience_eligible"] is False
    assert res["is_excluded"] is False


def test_hard_experience_exclusion_senior_title():
    svc = MatchingService()
    profile = create_mock_profile(experience_years=0)
    # Job title is Senior Lead Architect even if exp_min is low
    job_senior_title = create_mock_job(
        title="Senior Tech Lead (Python)",
        experience_min=1,
        experience_max=3,
    )

    res = svc.evaluate_job(job_senior_title, profile)
    assert res["experience_eligible"] is False
    assert res["is_excluded"] is False


def test_internship_matching_for_fresher():
    svc = MatchingService()
    profile = create_mock_profile(experience_years=0, internship_allowed=True)
    job_intern = create_mock_job(
        title="Python Backend Intern",
        employment_type="INTERNSHIP",
        experience_min=0,
        experience_max=0,
    )

    res = svc.evaluate_job(job_intern, profile)
    assert res["is_excluded"] is False
    assert res["overall_score"] > 60.0
    assert res["recommendation"] in ("STRONG_MATCH", "GOOD_MATCH")


def test_strict_location_exclusion():
    svc = MatchingService()
    profile = create_mock_profile(
        preferred_locations=["Delhi NCR", "Noida", "Gurugram"],
        remote_preference=True,
    )

    # 1. Onsite job outside preferred locations (Mumbai) marks location_eligible=False without dropping
    job_mumbai = create_mock_job(
        title="Backend Developer",
        location="Mumbai",
        remote_type="ONSITE",
    )
    res_mumbai = svc.evaluate_job(job_mumbai, profile, strict_location=True)
    assert res_mumbai["location_eligible"] is False
    assert res_mumbai["is_excluded"] is False

    # 2. Onsite job in Noida must be accepted
    job_noida = create_mock_job(
        title="Backend Developer",
        location="Noida",
        remote_type="ONSITE",
    )
    res_noida = svc.evaluate_job(job_noida, profile, strict_location=True)
    assert res_noida["is_excluded"] is False
    assert res_noida["overall_score"] > 50.0

    # 3. Remote job must be accepted even if company location is elsewhere
    job_remote = create_mock_job(
        title="Backend Developer",
        location="Work from home",
        remote_type="REMOTE",
    )
    res_remote = svc.evaluate_job(job_remote, profile, strict_location=True)
    assert res_remote["is_excluded"] is False
    assert res_remote["overall_score"] > 50.0


def test_regression_analytics_engineer_mismatch():
    """
    Test 1: Analytics Engineer mismatch
    Candidate has full-stack / backend web skills.
    Job is an Analytics Engineer requiring data stack (SQL, ETL, dbt, Snowflake, Airflow, Power BI, Data Warehousing).
    Must NOT be an 80-90% match. Gating and skill scoring must drop score significantly.
    """
    svc = MatchingService()
    profile = create_mock_profile(
        skills=["Python", "FastAPI", "React", "Node.js", "PostgreSQL", "Docker", "REST APIs"],
        target_roles=["Full Stack Developer", "Backend Developer", "AI Engineer"],
        preferred_locations=["Remote", "Bengaluru"],
    )
    job = create_mock_job(
        title="Analytics Engineer",
        company_name="DataVinci Private Limited",
        required_skills=["SQL", "ETL", "dbt", "Snowflake", "Airflow", "Power BI", "Data Warehousing"],
        preferred_skills=[],
        experience_min=0,
        experience_max=1,
        location="Work from home",
        remote_type="REMOTE",
    )

    res = svc.evaluate_job(job, profile)
    # Must NOT be an 80-90% match
    assert res["overall_score"] < 45.0
    assert res["recommendation"] in ("LOW_PRIORITY", "SKIP")
    assert len(res["required_skills"]["missing"]) >= 6


def test_regression_different_title_matching_skills():
    """
    Test 2: Different title, matching skills
    Job title is Analytics Engineer, but its requirements match candidate's actual skills.
    Must receive a strong match. Title must NOT reduce score.
    """
    svc = MatchingService()
    profile = create_mock_profile(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        preferred_locations=["Remote", "Bengaluru"],
    )
    job = create_mock_job(
        title="Analytics Engineer",
        company_name="TechCorp",
        required_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        preferred_skills=[],
        experience_min=0,
        experience_max=1,
        location="Remote",
        remote_type="REMOTE",
    )

    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] >= 80.0
    assert res["recommendation"] == "STRONG_MATCH"
    assert len(res["required_skills"]["matched"]) == 5
    assert len(res["required_skills"]["missing"]) == 0


def test_regression_generic_title_poor_skills():
    """
    Test 3: Generic title, poor skills
    Job title is attractive 'Software Engineer', but requirements are completely different stack (Java, Spring Boot, Kafka, Kubernetes, AWS).
    Must receive a low score (<30%), despite 'Software Engineer' title.
    """
    svc = MatchingService()
    profile = create_mock_profile(
        skills=["Python", "FastAPI", "React", "Node.js", "PostgreSQL"],
        preferred_locations=["Remote", "Bengaluru"],
    )
    job = create_mock_job(
        title="Software Engineer",
        company_name="EnterpriseCorp",
        required_skills=["Java", "Spring Boot", "Kafka", "Kubernetes", "AWS"],
        preferred_skills=[],
        experience_min=0,
        experience_max=1,
        location="Remote",
        remote_type="REMOTE",
    )

    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] <= 25.0
    assert res["recommendation"] == "SKIP"
    assert len(res["required_skills"]["matched"]) == 0


def test_regression_transferable_skill_partial_credit():
    """
    Test 4: Transferable skill partial credit
    Job requires FastAPI, candidate only has Python.
    Must receive partial transferable credit (0.5), NOT exact skill match (1.0).
    """
    svc = MatchingService()
    compat = svc.compute_skill_compatibility(
        candidate_skills=["Python"],
        required_skills=["FastAPI"],
        preferred_skills=[],
    )

    # FastAPI should NOT be in matched_required
    assert "FastAPI" not in compat["matched_required"]
    assert "FastAPI" in compat["missing_required"]

    # Must be in transferable_details with partial credit 0.5
    trans = compat["transferable_details"]
    assert len(trans) == 1
    assert trans[0]["job_skill"] == "FastAPI"
    assert trans[0]["candidate_skill"] == "Python"
    assert trans[0]["credit"] == 0.5


def test_regression_preferred_nice_to_have_not_penalizing():
    """
    Test 5: Nice-to-have skills
    Job requires: Python, PostgreSQL
    Preferred: AWS, Kubernetes, Terraform
    Candidate has: Python, PostgreSQL
    Expected: Strong match (>= 80%). Missing nice-to-have does NOT significantly penalize.
    """
    svc = MatchingService()
    profile = create_mock_profile(
        skills=["Python", "PostgreSQL"],
        preferred_locations=["Remote", "Bengaluru"],
    )
    job = create_mock_job(
        title="Python Backend Developer",
        company_name="StartupX",
        required_skills=["Python", "PostgreSQL"],
        preferred_skills=["AWS", "Kubernetes", "Terraform"],
        experience_min=0,
        experience_max=1,
        location="Remote",
        remote_type="REMOTE",
    )

    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] >= 80.0
    assert res["recommendation"] == "STRONG_MATCH"
    assert len(res["required_skills"]["matched"]) == 2
    assert len(res["required_skills"]["missing"]) == 0


def test_zero_required_skills_scoring_capped():
    """Jobs with 0 required skills must not get inflated STRONG_MATCH."""
    svc = MatchingService()
    profile = create_mock_profile(skills=["Python", "FastAPI"])
    job = create_mock_job(
        title="Software Engineer Intern",
        required_skills=[],
        preferred_skills=[],
    )
    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] <= 45.0
    assert res["recommendation"] in ["LOW_PRIORITY", "CONSIDER", "SKIP"]


def test_hard_role_eligibility_gate():
    """Unrelated roles without >=80% required skills match must be capped at <= 30.0 (SKIP)."""
    svc = MatchingService()
    profile = create_mock_profile(
        target_roles=["Backend Developer", "Full Stack Developer", "AI Engineer"],
        skills=["Python", "FastAPI", "React", "PostgreSQL"],
    )
    # Cyber Security Analyst with only Python matching
    job = create_mock_job(
        title="Cyber Security Analyst",
        required_skills=["Network Security", "Penetration Testing", "Python"],
        preferred_skills=[],
    )
    res = svc.evaluate_job(job, profile)
    assert res["overall_score"] <= 30.0
    assert res["recommendation"] == "SKIP"


def test_unpaid_internship_disqualified():
    """Unpaid internships must be disqualified when profile requires paid positions."""
    svc = MatchingService()
    profile = create_mock_profile(
        skills=["Python", "FastAPI"],
    )
    assert profile.minimum_salary_lpa is not None and profile.minimum_salary_lpa > 0
    job = create_mock_job(
        title="Backend Developer Intern",
        required_skills=["Python", "FastAPI"],
    )
    job.salary_raw = "Unpaid"
    res = svc.evaluate_job(job, profile)
    assert res["is_excluded"] is False


def test_evaluate_job_with_nullable_experience():
    """Ensure evaluate_job handles None experience values cleanly without crashing."""
    svc = MatchingService()
    profile = create_mock_profile()
    job = create_mock_job(
        title="Backend Developer (FastAPI)",
        required_skills=["Python", "FastAPI"],
        experience_min=None,
        experience_max=None,
    )
    res = svc.evaluate_job(job, profile)
    assert res["experience_score"] == 80.0
    assert "overall_score" in res
    assert res["overall_score"] > 0.0
