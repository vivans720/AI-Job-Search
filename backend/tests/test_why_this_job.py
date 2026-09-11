import pytest
from app.intelligence.service import AIService
from app.schemas.match import WhyThisJobResponse


@pytest.mark.asyncio
async def test_generate_why_this_job_strong_match_apply():
    service = AIService()
    
    match_breakdown = {
        "overall_score": 87.5,
        "recommendation": "STRONG_MATCH",
        "required_skills": {
            "matched": ["python", "fastapi", "postgresql"],
            "missing": ["kubernetes"],
        },
        "preferred_skills": {
            "matched": ["docker"],
            "missing": ["redis"],
        },
        "transferable_details": [
            {"candidate_skill": "flask", "job_skill": "rest apis", "credit": 0.8}
        ],
        "experience_eligible": True,
        "location_eligible": True,
        "confidence": 0.95,
        "confidence_label": "HIGH",
    }
    
    res: WhyThisJobResponse = await service.generate_why_this_job(
        job_id="test-job-123",
        job_title="Backend Engineer",
        company_name="Acme Corp",
        match_breakdown=match_breakdown,
        candidate_years=2.5,
        job_exp_min=2.0,
        job_exp_max=4.0,
        job_location="Bengaluru",
        job_remote_type="REMOTE",
        use_llm=False,
    )

    assert res.verdict == "APPLY"
    assert res.recommendation == "STRONG_MATCH"
    assert "python" in res.strong_matches
    assert "fastapi" in res.strong_matches
    assert "kubernetes" in res.missing_critical
    assert len(res.transferable_matches) == 1
    assert res.transferable_matches[0].job_skill == "rest apis"
    assert res.experience_status.eligible is True
    assert res.location_status.eligible is True
    assert len(res.interview_talking_points) >= 1
    assert "Acme Corp" in res.recommendation_text


@pytest.mark.asyncio
async def test_generate_why_this_job_mismatch_skip():
    service = AIService()
    
    match_breakdown = {
        "overall_score": 38.0,
        "recommendation": "SKIP",
        "required_skills": {
            "matched": ["git"],
            "missing": ["java", "spring boot"],
        },
        "preferred_skills": {
            "matched": [],
            "missing": ["kafka"],
        },
        "transferable_details": [],
        "experience_eligible": False,
        "location_eligible": False,
        "confidence": 0.9,
        "confidence_label": "HIGH",
    }
    
    res: WhyThisJobResponse = await service.generate_why_this_job(
        job_id="test-job-456",
        job_title="Senior Java Architect",
        company_name="Enterprise Systems",
        match_breakdown=match_breakdown,
        candidate_years=1.5,
        job_exp_min=5.0,
        job_exp_max=8.0,
        job_location="Mumbai",
        job_remote_type="ONSITE",
        candidate_preferred_locations=["Bengaluru"],
        candidate_remote_allowed=False,
        use_llm=False,
    )

    assert res.verdict == "SKIP"
    assert res.recommendation == "SKIP"
    assert "java" in res.missing_critical
    assert "spring boot" in res.missing_critical
    assert res.experience_status.eligible is False
    assert res.location_status.eligible is False
    assert len(res.rejection_reasons) >= 2
    assert "Skip" in res.recommendation_text


@pytest.mark.asyncio
async def test_generate_why_this_job_consider_bridgeable():
    service = AIService()
    
    match_breakdown = {
        "overall_score": 58.0,
        "recommendation": "CONSIDER",
        "required_skills": {
            "matched": ["python"],
            "missing": ["fastapi", "docker"],
        },
        "preferred_skills": {
            "matched": [],
            "missing": [],
        },
        "transferable_details": [
            {"candidate_skill": "flask", "job_skill": "fastapi", "credit": 0.5}
        ],
        "experience_eligible": True,
        "location_eligible": True,
        "confidence": 0.85,
        "confidence_label": "HIGH",
    }
    
    res: WhyThisJobResponse = await service.generate_why_this_job(
        job_id="test-job-789",
        job_title="Junior Backend Developer",
        company_name="FastScale",
        match_breakdown=match_breakdown,
        candidate_years=1.0,
        job_exp_min=1.0,
        job_exp_max=2.0,
        use_llm=False,
    )

    assert res.verdict == "CONSIDER"
    assert res.recommendation == "CONSIDER"
    assert len(res.transferable_matches) == 1
    assert "Consider" in res.recommendation_text
