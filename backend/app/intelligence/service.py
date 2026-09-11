from typing import Any
import structlog
from pydantic import BaseModel

from app.intelligence.base import BaseAIProvider
from app.intelligence.llm_provider import get_llm_provider
from app.utils.normalization import normalize_skills

logger = structlog.get_logger(__name__)


class SkillGapAnalysis(BaseModel):
    matched_skills: list[str]
    missing_critical_skills: list[str]
    missing_preferred_skills: list[str]
    learning_roadmap: list[dict[str, Any]]
    interview_talking_points: list[str]


class AIService:
    """High-level application intelligence service encapsulating domain AI tasks."""

    def __init__(self, provider: BaseAIProvider | None = None):
        self._provider = provider

    @property
    def provider(self) -> BaseAIProvider:
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    async def analyze_skill_gap(
        self, candidate_skills: list[str], job_required: list[str], job_preferred: list[str] | None = None
    ) -> SkillGapAnalysis:
        """Analyzes technical skill gaps and formulates bridge recommendations."""
        cand_norm = set(normalize_skills(candidate_skills))
        req_norm = set(normalize_skills(job_required))
        pref_norm = set(normalize_skills(job_preferred or []))

        matched = sorted(list(cand_norm.intersection(req_norm.union(pref_norm))))
        missing_req = sorted(list(req_norm.difference(cand_norm)))
        missing_pref = sorted(list(pref_norm.difference(cand_norm)))

        # Prompt AI to generate learning roadmap and talking points
        prompt = f"""You are a technical career advisor.
Candidate skills: {', '.join(candidate_skills)}
Job Required: {', '.join(job_required)}
Job Preferred: {', '.join(job_preferred or [])}

Missing Critical Skills: {', '.join(missing_req)}

Provide a structured bridging plan in valid JSON format:
{{
  "learning_roadmap": [
    {{"skill": "Skill Name", "action": "Specific project or tutorial action", "estimated_days": 3}}
  ],
  "interview_talking_points": [
    "How to address missing skill during interview"
  ]
}}
"""
        messages = [
            {"role": "system", "content": "You are a concise, practical technical mentor. Return JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            res = await self.provider.complete_json(messages)
            roadmap = res.get("learning_roadmap", [])
            talking_points = res.get("interview_talking_points", [])
        except Exception as e:
            logger.warning("skill_gap_ai_enrichment_fallback", error=str(e))
            roadmap = [{"skill": s, "action": f"Build a prototype with {s}", "estimated_days": 4} for s in missing_req[:3]]
            talking_points = [f"Highlight adjacent fundamentals when discussing {s}" for s in missing_req[:3]]

        return SkillGapAnalysis(
            matched_skills=matched,
            missing_critical_skills=missing_req,
            missing_preferred_skills=missing_pref,
            learning_roadmap=roadmap,
            interview_talking_points=talking_points,
        )

    async def generate_match_explanation(
        self, job_title: str, company: str, matched_skills: list[str], missing_skills: list[str]
    ) -> str:
        """Generates a motivating 2-sentence rationale for a match."""
        prompt = (
            f"Job: {job_title} at {company}.\n"
            f"Matched skills: {', '.join(matched_skills[:8])}.\n"
            f"Missing skills: {', '.join(missing_skills[:5])}.\n"
            "Generate a crisp 2-sentence rationale on why this job is worth applying to and how the candidate fits."
        )
        messages = [
            {"role": "system", "content": "You are a direct tech career coach. Write 2 punchy sentences."},
            {"role": "user", "content": prompt},
        ]
        try:
            return await self.provider.complete(messages, max_tokens=150)
        except Exception as e:
            logger.warning("generate_match_explanation_fallback", error=str(e))
            return f"Strong alignment in {', '.join(matched_skills[:3])}. Direct manual application recommended."
