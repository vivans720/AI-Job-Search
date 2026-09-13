import re
from typing import Any
from pydantic import BaseModel, Field
import structlog

from app.utils.normalization import (
    CANONICAL_SKILLS,
    extract_skills_from_text,
    normalize_skill,
    normalize_skills,
)

logger = structlog.get_logger(__name__)


def get_all_skill_forms(skill: str) -> set[str]:
    """Returns all lowercase lexical forms and canonical aliases for a skill."""
    clean = skill.strip().lower()
    canonical = normalize_skill(skill).strip().lower()
    forms = {clean, canonical}
    for alias, can in CANONICAL_SKILLS.items():
        if can.strip().lower() == canonical or alias.strip().lower() == clean:
            forms.add(alias.strip().lower())
            forms.add(can.strip().lower())
    return forms


def is_skill_present_in_text(
    skill: str,
    text: str,
    explicit_skills: list[str] | None = None,
) -> bool:
    """
    Verify that an extracted skill is genuinely grounded in the source text or explicit tags.
    Prevents LLM hallucinations of unmentioned technologies.
    """
    if not skill or not text:
        return False

    all_forms = get_all_skill_forms(skill)

    # 1. Match against explicit source tags
    if explicit_skills:
        for es in explicit_skills:
            es_forms = get_all_skill_forms(es)
            if all_forms & es_forms:
                return True

    text_lower = text.lower()

    # 2. Match any form against text with boundary
    for form in all_forms:
        if re.search(r"[^a-zA-Z0-9\s]", form):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(form)}(?![a-zA-Z0-9])"
        else:
            pattern = rf"\b{re.escape(form)}\b"
        if re.search(pattern, text_lower):
            return True

    return False


class SkillExtractionResult(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    method: str = "deterministic"  # "deterministic" | "llm_fallback" | "hybrid"
    confidence: float = 1.0
    raw_llm_response: dict[str, Any] | None = None


class JobSkillExtractionService:
    """
    Orchestrates job skill extraction:
    Runs fast deterministic extraction with canonical normalization and precedence rules.
    Zero LLM calls, avoiding rate limits and token costs.
    """

    def __init__(self, llm_provider: Any = None):
        # Kept for backward compatibility with existing constructor calls
        pass

    def should_trigger_llm(
        self,
        description: str,
        title: str | None,
        det_req: list[str],
        det_pref: list[str],
    ) -> bool:
        """LLM extraction disabled to avoid token usage and rate limits."""
        return False

    async def extract_skills(
        self,
        description: str,
        title: str | None = None,
        explicit_skills: list[str] | None = None,
    ) -> SkillExtractionResult:
        """
        Extract required and preferred skills deterministically with normalization.
        """
        det_req, det_pref = extract_skills_from_text(
            description=description,
            title=title,
            explicit_skills=explicit_skills,
        )

        norm_req = normalize_skills(det_req)
        norm_pref = normalize_skills(det_pref)

        # Precedence: required skills must not appear in preferred skills
        req_set = {s.lower() for s in norm_req}
        clean_pref = [s for s in norm_pref if s.lower() not in req_set]

        confidence = 0.95 if (norm_req or clean_pref) else 0.5

        return SkillExtractionResult(
            required_skills=norm_req,
            preferred_skills=clean_pref,
            nice_to_have_skills=[],
            method="deterministic",
            confidence=confidence,
        )



_skill_extraction_service: JobSkillExtractionService | None = None


def get_skill_extraction_service() -> JobSkillExtractionService:
    global _skill_extraction_service
    if _skill_extraction_service is None:
        _skill_extraction_service = JobSkillExtractionService()
    return _skill_extraction_service
