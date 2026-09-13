import pytest

from app.services.skill_extraction_service import (
    JobSkillExtractionService,
    SkillExtractionResult,
    is_skill_present_in_text,
)


@pytest.mark.asyncio
async def test_1_structured_description_deterministic():
    """
    Test 1 — Structured description:
    Clean section headers with required and preferred skills extracted deterministically.
    """
    service = JobSkillExtractionService()

    description = """
    Required Skills:
    Python
    FastAPI
    PostgreSQL

    Preferred:
    Docker
    AWS
    """
    res = await service.extract_skills(description=description, title="Software Engineer")

    assert res.method == "deterministic"
    assert "Python" in res.required_skills
    assert "FastAPI" in res.required_skills
    assert "PostgreSQL" in res.required_skills
    assert "Docker" in res.preferred_skills
    assert "AWS" in res.preferred_skills


@pytest.mark.asyncio
async def test_2_narrative_description_deterministic():
    """
    Test 2 — Narrative description:
    Requirements in text extracted deterministically without LLM.
    """
    service = JobSkillExtractionService()

    description = (
        "We're looking for a developer who will build APIs using "
        "Python and FastAPI. Experience with PostgreSQL is required. "
        "Knowledge of Docker and AWS would be a plus."
    )
    res = await service.extract_skills(description=description, title="Backend Developer")

    assert res.method == "deterministic"
    assert "Python" in res.required_skills
    assert "FastAPI" in res.required_skills
    assert "PostgreSQL" in res.required_skills
    # Unmentioned skills are never present
    assert "Kubernetes" not in res.required_skills


@pytest.mark.asyncio
async def test_3_duplicate_normalization():
    """
    Test 3 — Duplicate normalization:
    Aliases like React, ReactJS, React.js map to canonical React.
    """
    service = JobSkillExtractionService()

    description = "Frontend engineer proficient in React, ReactJS, and React.js."
    res = await service.extract_skills(description=description)

    assert res.required_skills == ["React"]


@pytest.mark.asyncio
async def test_4_required_takes_precedence_over_preferred():
    """
    Test 4 — Required takes precedence:
    If a skill appears in both required and preferred, keep in required only.
    """
    service = JobSkillExtractionService()

    description = """
    Requirements:
    Python

    Preferred:
    Python
    Docker
    """
    res = await service.extract_skills(description=description)

    assert res.required_skills == ["Python"]
    assert res.preferred_skills == ["Docker"]
    assert "Python" not in res.preferred_skills


@pytest.mark.asyncio
async def test_5_title_must_not_hallucinate_skills():
    """
    Test 5 — Title must not hallucinate unmentioned skills:
    Generic role title words (AI, ML) do not add unmentioned technologies.
    """
    service = JobSkillExtractionService()

    title = "Senior AI Engineer"
    description = "Work with SQL and Power BI to build analytics dashboards."
    res = await service.extract_skills(description=description, title=title)

    assert "SQL" in res.required_skills
    assert "Power BI" in res.required_skills
    for unmentioned in ["PyTorch", "TensorFlow"]:
        assert unmentioned not in res.required_skills
        assert unmentioned not in res.preferred_skills



def test_is_skill_present_in_text_helper():
    """Unit test for anti-hallucination boundary detection helper."""
    text = "Looking for an engineer who knows PostgreSQL, React.js, and Docker."
    assert is_skill_present_in_text("PostgreSQL", text) is True
    assert is_skill_present_in_text("postgres", text) is True
    assert is_skill_present_in_text("React", text) is True
    assert is_skill_present_in_text("Docker", text) is True
    assert is_skill_present_in_text("Kubernetes", text) is False
    assert is_skill_present_in_text("AWS", text) is False
    # Anti-substring false positive check (rag should not match inside storage)
    text2 = "Experience with cloud storage solutions."
    assert is_skill_present_in_text("RAG", text2) is False
