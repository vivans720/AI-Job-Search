import asyncio
import re
from typing import Any
from pydantic import BaseModel, Field
import structlog

from app.config import settings
from app.intelligence.llm_provider import LLMProvider, get_llm_provider
from app.utils.normalization import (
    CANONICAL_SKILLS,
    extract_skills_from_text,
    normalize_skill,
    normalize_skills,
)

logger = structlog.get_logger(__name__)

GENERIC_SOFT_SKILLS: set[str] = {
    "communication",
    "communication skills",
    "good communication",
    "verbal communication",
    "written communication",
    "strong communication",
    "interpersonal skills",
    "interpersonal",
    "teamwork",
    "team player",
    "collaboration",
    "collaborative",
    "problem solving",
    "problem-solving",
    "critical thinking",
    "analytical thinking",
    "analytical skills",
    "troubleshooting skills",
    "leadership",
    "leadership skills",
    "mentorship",
    "management",
    "project management",
    "time management",
    "multitasking",
    "work ethic",
    "attention to detail",
    "fast learner",
    "quick learner",
    "eager to learn",
    "willingness to learn",
    "adaptability",
    "self-motivated",
    "self motivated",
    "self-starter",
    "creativity",
    "creative thinking",
    "ownership",
    "accountability",
    "flexibility",
    "enthusiasm",
    "presentation skills",
    "negotiation",
    "decision making",
    "positive attitude",
    "good attitude",
    "ability to work independently",
    "working independently",
    "independent worker",
}

SYSTEM_EXTRACTION_PROMPT = """You are an expert technical job-description skill extractor.
Your task is to extract only concrete technical skills explicitly required or preferred in the job description.

STRICT RULES:
1. Extract ONLY technical skills that are explicitly mentioned in the job description.
2. Do NOT evaluate the candidate or calculate match scores.
3. Do NOT use the job title to infer skills not explicitly stated in the description (e.g. do not assume an 'AI Engineer' requires Python or PyTorch unless written in the text).
4. Do NOT invent technologies or infer unstated requirements.
5. Do NOT include generic soft skills or personal traits (exclude Communication, Teamwork, Problem Solving, Leadership, Adaptability).
6. Classify each technical skill into:
   - required_skills: mandatory for the role (must have, required, mandatory, essential, proficiency in).
   - preferred_skills: advantageous but not mandatory (preferred, plus, bonus, nice to have, good to have, advantage).
   - nice_to_have_skills: optional bonus skills.
7. If wording is ambiguous or uncertain, be conservative and omit the skill.
8. Return valid JSON only with keys: required_skills, preferred_skills, nice_to_have_skills, confidence.
"""


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
    1. Runs fast deterministic extraction first.
    2. Decides if LLM fallback is needed (zero skills, low coverage, narrative ambiguity).
    3. Executes structured LLM completion with strict anti-hallucination and soft-skill guards.
    4. Applies centralized canonical normalization and precedence rules.
    5. Gracefully falls back to deterministic extraction on timeout or failure.
    """

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._llm = llm_provider

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    def should_trigger_llm(
        self,
        description: str,
        title: str | None,
        det_req: list[str],
        det_pref: list[str],
    ) -> bool:
        """Determines whether the LLM fallback is needed."""
        if not settings.LLM_SKILL_EXTRACTION_ENABLED:
            return False

        desc = (description or "").strip()
        if len(desc) < 30:
            return False

        total_skills = len(det_req) + len(det_pref)

        # Only trigger slow LLM if deterministic extractor found zero skills in a substantial description
        if total_skills == 0 and len(desc) >= settings.LLM_SKILL_EXTRACTION_MIN_DESCRIPTION_LENGTH:
            return True

        return False

    async def extract_skills(
        self,
        description: str,
        title: str | None = None,
        explicit_skills: list[str] | None = None,
    ) -> SkillExtractionResult:
        """
        Extract required and preferred skills with fallback and normalization.
        """
        # 1. Deterministic first pass
        det_req, det_pref = extract_skills_from_text(
            description=description,
            title=title,
            explicit_skills=explicit_skills,
        )

        # 2. Check if LLM fallback should run
        if not self.should_trigger_llm(description, title, det_req, det_pref):
            return SkillExtractionResult(
                required_skills=det_req,
                preferred_skills=det_pref,
                nice_to_have_skills=[],
                method="deterministic",
                confidence=0.95 if (det_req or det_pref) else 0.5,
            )

        # 3. LLM Fallback Execution
        logger.info(
            "llm_skill_extraction_triggered",
            title=title,
            desc_len=len(description or ""),
            det_req_count=len(det_req),
            det_pref_count=len(det_pref),
        )

        user_prompt = (
            f"Job Title (for context only - DO NOT infer unstated skills from title): {title or 'Not specified'}\n\n"
            f"--- JOB DESCRIPTION ---\n{description}\n--- END JOB DESCRIPTION ---\n\n"
            "Extract the technical skills and return valid JSON matching the specified schema."
        )

        try:
            messages = [
                {"role": "system", "content": SYSTEM_EXTRACTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            raw_res = await asyncio.wait_for(
                self.llm.complete_json(messages),
                timeout=settings.LLM_SKILL_EXTRACTION_TIMEOUT,
            )

            return self._process_llm_response(
                raw_res=raw_res,
                description=description,
                title=title,
                explicit_skills=explicit_skills,
                det_req=det_req,
                det_pref=det_pref,
            )

        except Exception as e:
            logger.warning(
                "llm_skill_extraction_failed_fallback_deterministic",
                error=str(e),
                title=title,
            )
            # Safe graceful degradation: return deterministic result
            return SkillExtractionResult(
                required_skills=det_req,
                preferred_skills=det_pref,
                nice_to_have_skills=[],
                method="deterministic",
                confidence=0.5,
            )

    def _process_llm_response(
        self,
        raw_res: dict[str, Any],
        description: str,
        title: str | None,
        explicit_skills: list[str] | None,
        det_req: list[str],
        det_pref: list[str],
    ) -> SkillExtractionResult:
        """
        Validates, sanitizes, and normalizes raw LLM response.
        Applies anti-hallucination and precedence guards.
        """
        if not isinstance(raw_res, dict):
            return SkillExtractionResult(
                required_skills=det_req,
                preferred_skills=det_pref,
                nice_to_have_skills=[],
                method="deterministic",
                confidence=0.5,
            )

        raw_req = raw_res.get("required_skills") or []
        raw_pref = raw_res.get("preferred_skills") or []
        raw_nice = raw_res.get("nice_to_have_skills") or []

        if not isinstance(raw_req, list):
            raw_req = []
        if not isinstance(raw_pref, list):
            raw_pref = []
        if not isinstance(raw_nice, list):
            raw_nice = []

        confidence_val = raw_res.get("confidence")
        try:
            confidence = float(confidence_val) if confidence_val is not None else 0.85
            confidence = max(0.1, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.85

        # Filter function for valid technical skills
        def filter_and_ground(items: list[Any]) -> list[str]:
            grounded = []
            for item in items:
                if not isinstance(item, str):
                    continue
                s = item.strip()
                if not s:
                    continue
                # Reject soft skills
                if s.lower() in GENERIC_SOFT_SKILLS:
                    continue
                # Reject hallucinations (must appear in description or explicit tags)
                if not is_skill_present_in_text(s, description, explicit_skills):
                    continue
                grounded.append(s)
            return grounded

        valid_llm_req = filter_and_ground(raw_req)
        valid_llm_pref = filter_and_ground(raw_pref)
        valid_llm_nice = filter_and_ground(raw_nice)

        # 4. Canonical normalization
        norm_llm_req = normalize_skills(valid_llm_req)
        norm_llm_pref = normalize_skills(valid_llm_pref)
        norm_llm_nice = normalize_skills(valid_llm_nice)

        # 5. Precedence rule: required > preferred > nice_to_have
        req_set = {s.lower() for s in norm_llm_req}
        clean_llm_pref = [s for s in norm_llm_pref if s.lower() not in req_set]
        pref_set = {s.lower() for s in clean_llm_pref} | req_set
        clean_llm_nice = [s for s in norm_llm_nice if s.lower() not in pref_set]

        # Combine preferred and nice-to-have for downstream scoring
        combined_llm_pref = normalize_skills(clean_llm_pref + clean_llm_nice)

        # 6. Hybrid merge strategy:
        # Check if description contained an explicit section header for preferred skills
        has_explicit_pref_section = bool(
            re.search(
                r"(?:^|\n)\s*(?:(?:good|nice)\s+to\s+have|preferred(?:\s+qualifications|\s+skills)?|bonus\s+points?|plus\s+points?|desired\s+skills|optional\s+skills)[:\s\-]",
                description or "",
                re.IGNORECASE,
            )
        )

        explicit_norm = normalize_skills(explicit_skills or [])

        if has_explicit_pref_section:
            # Deterministic explicit sections are trusted
            final_req = normalize_skills(det_req + norm_llm_req + explicit_norm)
            final_req_set = {s.lower() for s in final_req}
            final_pref = [
                s
                for s in normalize_skills(det_pref + combined_llm_pref)
                if s.lower() not in final_req_set
            ]
        else:
            # Narrative text: LLM classification establishes required vs preferred
            final_req = normalize_skills(norm_llm_req + explicit_norm)
            final_req_set = {s.lower() for s in final_req}
            final_pref = [
                s
                for s in combined_llm_pref
                if s.lower() not in final_req_set
            ]

        # Determine provenance method
        if len(det_req) == 0 and len(det_pref) == 0:
            method = "llm_fallback"
        else:
            method = "hybrid"

        return SkillExtractionResult(
            required_skills=final_req,
            preferred_skills=final_pref,
            nice_to_have_skills=clean_llm_nice,
            method=method,
            confidence=confidence,
            raw_llm_response=raw_res,
        )


_skill_extraction_service: JobSkillExtractionService | None = None


def get_skill_extraction_service() -> JobSkillExtractionService:
    global _skill_extraction_service
    if _skill_extraction_service is None:
        _skill_extraction_service = JobSkillExtractionService()
    return _skill_extraction_service
