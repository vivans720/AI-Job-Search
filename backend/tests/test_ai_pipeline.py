import pytest
from unittest.mock import AsyncMock, MagicMock
from app.intelligence.service import AIService
from app.intelligence.schemas import (
    CandidateProfileOutput,
    JobSkillsOutput,
    SkillNormalizationOutput,
    JobEnrichmentOutput,
)


@pytest.mark.asyncio
async def test_extract_candidate_profile_structured():
    mock_provider = MagicMock()
    mock_provider.complete_json = AsyncMock(return_value={
        "candidate_name": "Jane Doe",
        "email": "jane@example.com",
        "experience_level": "FRESHER",
        "experience_years": 0,
        "target_roles": ["Backend Developer", "Full Stack Developer"],
        "programming_languages": ["Python", "js"],
        "frameworks": ["FastAPI", "reactjs"],
        "databases": ["PostgreSQL"],
        "cloud": ["Docker"],
        "tools": ["Git"],
        "skills": ["REST APIs"],
        "education": [{"degree": "B.Tech CS", "institution": "Tech Univ", "graduation_year": 2026}],
        "projects": [{"title": "Job Finder", "description": "Search engine", "technologies": ["Python", "FastAPI"]}],
        "work_experience": [],
        "certifications": [],
        "preferred_locations": ["Bengaluru", "Remote"],
        "summary": "Motivated backend developer building scalable microservices."
    })

    service = AIService(provider=mock_provider)
    profile = await service.extract_candidate_profile("Sample resume text")

    assert isinstance(profile, CandidateProfileOutput)
    assert profile.candidate_name == "Jane Doe"
    assert "JavaScript" in profile.programming_languages  # Normalized from 'js'
    assert "React" in profile.frameworks  # Normalized from 'reactjs'
    assert profile.experience_level == "FRESHER"

    # Test fractional experience_years (e.g. 0.5 from internship)
    mock_provider.complete_json = AsyncMock(return_value={
        "candidate_name": "Candidate",
        "experience_years": 0.5,
        "skills": ["Python"],
    })
    p2 = await service.extract_candidate_profile("Internship resume text")
    assert p2.experience_years == 0.5
    assert p2.candidate_name == "Candidate"


@pytest.mark.asyncio
async def test_normalize_skills_canonical_dict():
    service = AIService()
    # "react.js", "py", "postgres" should resolve directly via canonical dict without provider
    result = await service.normalize_skills_llm(["react.js", "py", "postgres"])
    assert isinstance(result, SkillNormalizationOutput)
    mapping_dict = {m.raw_token: m.canonical_skill for m in result.mappings}
    assert mapping_dict["react.js"] == "React"
    assert mapping_dict["py"] == "Python"
    assert mapping_dict["postgres"] == "PostgreSQL"


@pytest.mark.asyncio
async def test_extract_job_skills_hybrid():
    mock_provider = MagicMock()
    mock_provider.complete_json = AsyncMock(return_value={
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker", "Kubernetes"],
        "tools_and_technologies": ["PostgreSQL", "Git"],
        "soft_skills": ["Teamwork"]
    })

    service = AIService(provider=mock_provider)
    result = await service.extract_job_skills(
        title="Backend Engineer",
        description="Looking for Python and FastAPI developer with Docker and k8s experience."
    )

    assert isinstance(result, JobSkillsOutput)
    assert "Python" in result.required_skills
    assert "FastAPI" in result.required_skills
    assert "Teamwork" in result.soft_skills


@pytest.mark.asyncio
async def test_enrich_job():
    mock_provider = MagicMock()
    mock_provider.complete_json = AsyncMock(return_value={
        "standardized_title": "Software Development Engineer I",
        "role_category": "BACKEND",
        "seniority": "ENTRY_LEVEL",
        "min_experience_years": 0,
        "max_experience_years": 1,
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["AWS"],
        "core_responsibilities": ["Build APIs", "Write tests"],
        "requirements_summary": ["B.Tech CS", "Strong Python knowledge"],
        "tech_stack": ["Python", "PostgreSQL", "Docker"],
        "remote_policy_reasoning": "Hybrid 2 days in office"
    })

    service = AIService(provider=mock_provider)
    enrichment = await service.enrich_job(
        title="Python Backend Intern",
        description="Write high performance async APIs using FastAPI and PostgreSQL."
    )

    assert isinstance(enrichment, JobEnrichmentOutput)
    assert enrichment.standardized_title == "Software Development Engineer I"
    assert enrichment.role_category == "BACKEND"
    assert enrichment.min_experience_years == 0
    assert "Python" in enrichment.required_skills
