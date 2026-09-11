import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.intelligence.llm_provider import LLMProvider
from app.services.skill_extraction_service import (
    JobSkillExtractionService,
    SkillExtractionResult,
    is_skill_present_in_text,
)


class MockLLM(LLMProvider):
    def __init__(self, return_value: dict | None = None, should_fail: bool = False, delay: float = 0.0):
        self.return_value = return_value or {}
        self.should_fail = should_fail
        self.delay = delay
        self.call_count = 0
        self.last_messages = None

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        return ""

    async def complete_json(self, messages: list[dict[str, str]], schema=None, **kwargs) -> dict:
        self.call_count += 1
        self.last_messages = messages
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.should_fail:
            raise RuntimeError("OmniRoute connection timed out")
        return self.return_value


@pytest.mark.asyncio
async def test_1_structured_description_no_llm_call():
    """
    Test 1 — Structured description:
    Clean section headers with required and preferred skills.
    Deterministic extractor handles it; LLM must NOT be called.
    """
    mock_llm = MockLLM()
    service = JobSkillExtractionService(llm_provider=mock_llm)

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

    assert mock_llm.call_count == 0
    assert res.method == "deterministic"
    assert "Python" in res.required_skills
    assert "FastAPI" in res.required_skills
    assert "PostgreSQL" in res.required_skills
    assert "Docker" in res.preferred_skills
    assert "AWS" in res.preferred_skills


@pytest.mark.asyncio
async def test_2_narrative_description_llm_fallback_triggered():
    """
    Test 2 — Narrative description:
    Requirements embedded in conversational text with 'plus'.
    LLM fallback is triggered and correctly separates required and preferred.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker", "AWS"],
            "nice_to_have_skills": [],
            "confidence": 0.95,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = (
        "We're looking for a developer who will build APIs using "
        "Python and FastAPI. Experience with PostgreSQL is required. "
        "Knowledge of Docker and AWS would be a plus."
    )
    res = await service.extract_skills(description=description, title="Backend Developer")

    assert mock_llm.call_count == 1
    assert set(res.required_skills) == {"Python", "FastAPI", "PostgreSQL"}
    assert set(res.preferred_skills) == {"Docker", "AWS"}
    assert res.method in ("llm_fallback", "hybrid")


@pytest.mark.asyncio
async def test_3_no_hallucination_rejects_unmentioned_skills():
    """
    Test 3 — No hallucination:
    LLM returns technologies that were never mentioned in the job text.
    Anti-hallucination verification must strip them.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": [
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Docker",
                "AWS",
                "Redis",
                "Kubernetes",
            ],
            "preferred_skills": [],
            "confidence": 0.9,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    # Only Python and FastAPI are in the text
    description = "Build web APIs using Python and FastAPI."
    res = await service.extract_skills(description=description, title="Python Developer")

    assert set(res.required_skills) == {"Python", "FastAPI"}
    for unmentioned in ["PostgreSQL", "Docker", "AWS", "Redis", "Kubernetes"]:
        assert unmentioned not in res.required_skills
        assert unmentioned not in res.preferred_skills


@pytest.mark.asyncio
async def test_4_preferred_classification_from_narrative():
    """
    Test 4 — Preferred classification:
    Distinguish between mandatory and preferred/plus skills.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": ["Python", "PostgreSQL"],
            "preferred_skills": ["Docker", "AWS"],
            "nice_to_have_skills": [],
            "confidence": 0.92,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = (
        "Python and PostgreSQL are required. "
        "Docker experience is preferred. "
        "AWS knowledge is a plus."
    )
    res = await service.extract_skills(description=description)

    assert set(res.required_skills) == {"Python", "PostgreSQL"}
    assert set(res.preferred_skills) == {"Docker", "AWS"}


@pytest.mark.asyncio
async def test_5_llm_failure_graceful_deterministic_fallback():
    """
    Test 5 — LLM failure:
    Mock OmniRoute timeout/error. Job ingestion must NOT fail.
    Deterministic skills preserved.
    """
    mock_llm = MockLLM(should_fail=True)
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = (
        "We are looking for an engineer with Python and PostgreSQL knowledge. "
        "Docker knowledge is a plus."
    )
    res = await service.extract_skills(description=description, title="Engineer")

    # Pipeline does not raise
    assert isinstance(res, SkillExtractionResult)
    assert res.method == "deterministic"
    # Deterministic found Python and PostgreSQL
    assert "Python" in res.required_skills
    assert "PostgreSQL" in res.required_skills


@pytest.mark.asyncio
async def test_6_malformed_llm_json_fallback():
    """
    Test 6 — Malformed LLM JSON:
    LLM returns invalid structure or non-dict. Falls back cleanly.
    """
    mock_llm = MockLLM(return_value="This job requires Python and FastAPI.")  # type: ignore
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = (
        "Looking for Python and FastAPI developer with database skills. "
        "Docker would be a bonus."
    )
    res = await service.extract_skills(description=description)

    assert isinstance(res, SkillExtractionResult)
    assert res.method == "deterministic"
    assert "Python" in res.required_skills


@pytest.mark.asyncio
async def test_7_duplicate_normalization():
    """
    Test 7 — Duplicate normalization:
    LLM returns aliases like React, ReactJS, React.js.
    All must map to canonical [React].
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": ["React", "ReactJS", "React.js"],
            "preferred_skills": [],
            "confidence": 0.9,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = "Frontend engineer proficient in React, ReactJS, and React.js."
    res = await service.extract_skills(description=description)

    assert res.required_skills == ["React"]


@pytest.mark.asyncio
async def test_8_required_takes_precedence_over_preferred():
    """
    Test 8 — Required takes precedence:
    If a skill appears in both required and preferred, keep it in required only.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": ["Python"],
            "preferred_skills": ["Python", "Docker"],
            "confidence": 0.9,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = "We need Python expertise. Python and Docker are also desirable."
    res = await service.extract_skills(description=description)

    assert res.required_skills == ["Python"]
    assert res.preferred_skills == ["Docker"]
    assert "Python" not in res.preferred_skills


@pytest.mark.asyncio
async def test_9_generic_soft_skills_excluded():
    """
    Test 9 — Generic soft skills excluded:
    Soft skills like 'Communication', 'Teamwork', 'Problem Solving' stripped.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": [
                "Python",
                "Communication",
                "Teamwork",
                "FastAPI",
                "Problem Solving",
            ],
            "preferred_skills": ["Leadership", "Time Management", "Docker"],
            "confidence": 0.9,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    description = (
        "Requirements: Python and FastAPI with good communication, teamwork, and problem solving skills. "
        "Leadership and Docker are a plus."
    )
    res = await service.extract_skills(description=description)

    assert set(res.required_skills) == {"Python", "FastAPI"}
    assert res.preferred_skills == ["Docker"]
    for soft in ["Communication", "Teamwork", "Problem Solving", "Leadership", "Time Management"]:
        assert soft not in res.required_skills
        assert soft not in res.preferred_skills


@pytest.mark.asyncio
async def test_10_title_must_not_influence_extraction():
    """
    Test 10 — Title must not influence extraction:
    Title 'Senior AI Engineer' must not cause AI/PyTorch/LLM to be extracted
    when description only requires SQL and Power BI.
    """
    mock_llm = MockLLM(
        return_value={
            "required_skills": ["SQL", "Power BI"],
            "preferred_skills": [],
            "confidence": 0.95,
        }
    )
    service = JobSkillExtractionService(llm_provider=mock_llm)

    title = "Senior AI Engineer"
    description = "Work with SQL and Power BI to build analytics dashboards."
    res = await service.extract_skills(description=description, title=title)

    assert "SQL" in res.required_skills
    assert "Power BI" in res.required_skills
    # Unmentioned AI technologies must not be hallucinated
    for ai_skill in ["Python", "PyTorch", "TensorFlow", "LLM", "Artificial Intelligence"]:
        assert ai_skill not in res.required_skills
        assert ai_skill not in res.preferred_skills


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
