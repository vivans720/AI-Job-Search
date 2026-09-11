from typing import Any
import structlog
from pydantic import BaseModel

from app.intelligence.base import BaseAIProvider
from app.intelligence.llm_provider import get_llm_provider
from app.intelligence.schemas import (
    CandidateProfileOutput,
    JobSkillsOutput,
    SkillNormalizationOutput,
    JobEnrichmentOutput,
)
from app.schemas.match import (
    ExperienceStatus,
    LocationStatus,
    TransferableMatchItem,
    WhyThisJobResponse,
)
from app.utils.normalization import (
    normalize_skills,
    normalize_skill,
    normalize_title,
    infer_experience_from_title,
    extract_skills_from_text,
    CANONICAL_SKILLS,
)

logger = structlog.get_logger(__name__)


class SkillGapAnalysis(BaseModel):
    matched_skills: list[str]
    missing_critical_skills: list[str]
    missing_preferred_skills: list[str]
    learning_roadmap: list[dict[str, Any]]
    interview_talking_points: list[str]


class AIService:
    """High-level application intelligence service encapsulating domain AI pipeline tasks."""

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

    async def extract_candidate_profile(self, resume_text: str) -> CandidateProfileOutput:
        """Phase 40: Extracts high-precision structured candidate profile using LLM with Pydantic output."""
        prompt = f"""You are an expert technical candidate profiler and resume analyst.
Analyze the provided resume text and extract a comprehensive, structured candidate profile.

Guidelines:
1. Do NOT hallucinate information not present in the resume.
2. For fresh graduates / current students with only internships, set experience_level="FRESHER" and experience_years=0.
3. Categorize technologies cleanly into programming_languages, frameworks, databases, cloud, tools, and general skills.
4. Return a valid JSON object matching the requested schema:
{{
  "candidate_name": "Full Name",
  "email": "email or null",
  "experience_level": "FRESHER" or "ENTRY_LEVEL" or "MID" or "SENIOR",
  "experience_years": 0,
  "target_roles": ["Full Stack Developer", "Backend Developer"],
  "programming_languages": ["Python", "JavaScript"],
  "frameworks": ["FastAPI", "React"],
  "databases": ["PostgreSQL"],
  "cloud": ["AWS", "Docker"],
  "tools": ["Git", "Linux"],
  "skills": ["REST APIs", "System Design"],
  "education": [{{"degree": "B.Tech", "institution": "College", "graduation_year": 2026, "grade": null}}],
  "projects": [{{"title": "Project Name", "description": "Details", "technologies": ["Python"], "link": null}}],
  "work_experience": [{{"title": "Intern", "company": "Company", "duration": "3 months", "description": "Details", "type": "INTERNSHIP"}}],
  "certifications": [],
  "preferred_locations": ["Remote", "Bengaluru"],
  "summary": "2-sentence summary"
}}

--- RESUME TEXT ---
{resume_text}
--- END RESUME ---
"""
        messages = [
            {"role": "system", "content": "You are a technical resume analysis engine. Output JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            data = await self.provider.complete_json(messages)
            # Normalize all skill lists
            for key in ("programming_languages", "frameworks", "databases", "cloud", "tools"):
                if key in data and isinstance(data[key], list):
                    data[key] = normalize_skills(data[key])
            
            combined = []
            for key in ("programming_languages", "frameworks", "databases", "cloud", "tools", "skills"):
                if key in data and isinstance(data[key], list):
                    combined.extend(data[key])
            data["skills"] = normalize_skills(combined)

            return CandidateProfileOutput(**data)
        except Exception as e:
            logger.warning("ai_extract_candidate_profile_fallback", error=str(e))
            # Minimal deterministic fallback
            return CandidateProfileOutput(
                candidate_name="Candidate",
                experience_level="FRESHER",
                experience_years=0,
                skills=normalize_skills([s for s in resume_text.split() if s.lower() in CANONICAL_SKILLS][:10]),
                summary="Profile parsed via fallback.",
            )

    async def extract_job_skills(self, title: str, description: str) -> JobSkillsOutput:
        """Phase 40: Extracts required vs preferred technical and soft skills using LLM with regex fallback."""
        prompt = f"""Analyze this job posting and extract all required skills, preferred/bonus skills, tools/technologies, and soft skills.
Job Title: {title}
Job Description:
{description[:4000]}

Return JSON:
{{
  "required_skills": ["Must have technical skills"],
  "preferred_skills": ["Nice to have / bonus skills"],
  "tools_and_technologies": ["Specific tools, platforms, or cloud services"],
  "soft_skills": ["Communication", "Problem Solving", etc]
}}
"""
        messages = [
            {"role": "system", "content": "You are an expert technical recruiter analyzing job descriptions. Return JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            data = await self.provider.complete_json(messages)
            req = normalize_skills(data.get("required_skills", []))
            pref = normalize_skills(data.get("preferred_skills", []))
            tools = normalize_skills(data.get("tools_and_technologies", []))
            soft = [s.strip() for s in data.get("soft_skills", []) if s.strip()]

            # Fallback augment from regex scan if LLM returned too few skills
            regex_req, regex_pref = extract_skills_from_text(description, title=title)
            final_req = normalize_skills(req + regex_req)
            final_pref = [p for p in normalize_skills(pref + regex_pref) if p.lower() not in {r.lower() for r in final_req}]

            return JobSkillsOutput(
                required_skills=final_req,
                preferred_skills=final_pref,
                tools_and_technologies=tools,
                soft_skills=soft,
            )
        except Exception as e:
            logger.warning("ai_extract_job_skills_fallback", error=str(e))
            regex_req, regex_pref = extract_skills_from_text(description, title=title)
            return JobSkillsOutput(
                required_skills=regex_req,
                preferred_skills=regex_pref,
                tools_and_technologies=[],
                soft_skills=[],
            )

    async def normalize_skills_llm(self, ambiguous_skills: list[str]) -> SkillNormalizationOutput:
        """Phase 40: Canonicalizes ambiguous, variant, or slang skill names to canonical industry standard names."""
        if not ambiguous_skills:
            return SkillNormalizationOutput(mappings=[])

        # Check existing dictionary first
        unresolved: list[str] = []
        resolved_mappings: list[dict[str, str]] = []

        for raw in ambiguous_skills:
            raw_clean = raw.strip()
            if not raw_clean:
                continue
            canonical = normalize_skill(raw_clean)
            if canonical.lower() != raw_clean.lower() or raw_clean.lower() in CANONICAL_SKILLS:
                resolved_mappings.append({"raw_token": raw_clean, "canonical_skill": canonical})
            else:
                unresolved.append(raw_clean)

        if not unresolved:
            return SkillNormalizationOutput(mappings=resolved_mappings)

        # Prompt LLM to resolve ambiguous ones
        prompt = f"""You are a tech taxonomy normalizer. Map each variant/spelling/raw skill to its single canonical industry standard skill name.
Examples:
- "React.js", "ReactJS", "react" -> "React"
- "k8s" -> "Kubernetes"
- "postgres" -> "PostgreSQL"
- "fast api" -> "FastAPI"
- "py" -> "Python"

Map these terms:
{', '.join(unresolved)}

Return JSON:
{{
  "mappings": [
    {{"raw_token": "raw input string", "canonical_skill": "Canonical Name"}}
  ]
}}
"""
        messages = [
            {"role": "system", "content": "You are a precise technical dictionary standardizer. Output JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            data = await self.provider.complete_json(messages)
            llm_mappings = data.get("mappings", [])
            for item in llm_mappings:
                raw_t = item.get("raw_token", "").strip()
                can_s = item.get("canonical_skill", "").strip()
                if raw_t and can_s:
                    resolved_mappings.append({"raw_token": raw_t, "canonical_skill": can_s})
        except Exception as e:
            logger.warning("ai_normalize_skills_llm_fallback", error=str(e))
            for raw in unresolved:
                resolved_mappings.append({"raw_token": raw, "canonical_skill": normalize_skill(raw)})

        return SkillNormalizationOutput(mappings=resolved_mappings)

    async def enrich_job(self, title: str, description: str, raw_data: dict[str, Any] | None = None) -> JobEnrichmentOutput:
        """Phase 40: Deep LLM-driven job enrichment (role standardization, seniority, requirements, tech stack)."""
        prompt = f"""Enrich this job posting into a structured intelligence object.
Job Title: {title}
Job Description:
{description[:4000]}

Extract:
1. standardized_title (e.g. 'Software Development Engineer I', 'Backend Developer')
2. role_category (one of: SOFTWARE_ENGINEERING, FULL_STACK, BACKEND, FRONTEND, AI_ENGINEERING, ML_ENGINEERING, GEN_AI, DATA, DEVOPS)
3. seniority (FRESHER, ENTRY_LEVEL, MID, SENIOR, LEAD)
4. min_experience_years (integer or null)
5. max_experience_years (integer or null)
6. required_skills (top required technical skills)
7. preferred_skills (bonus skills)
8. core_responsibilities (3-5 crisp bullet points)
9. requirements_summary (3-5 crisp requirement bullet points)
10. tech_stack (list of languages, libraries, platforms)
11. remote_policy_reasoning (short explanation of why ONSITE/REMOTE/HYBRID)

Return JSON:
{{
  "standardized_title": "...",
  "role_category": "...",
  "seniority": "...",
  "min_experience_years": 0,
  "max_experience_years": 2,
  "required_skills": [],
  "preferred_skills": [],
  "core_responsibilities": [],
  "requirements_summary": [],
  "tech_stack": [],
  "remote_policy_reasoning": "..."
}}
"""
        messages = [
            {"role": "system", "content": "You are a senior technical hiring manager analyzing job specifications. Return JSON only."},
            {"role": "user", "content": prompt},
        ]

        norm_title, inferred_cat = normalize_title(title)
        min_exp, max_exp, _, _ = infer_experience_from_title(title)

        try:
            data = await self.provider.complete_json(messages)
            # Ensure skills are normalized
            data["required_skills"] = normalize_skills(data.get("required_skills", []))
            data["preferred_skills"] = normalize_skills(data.get("preferred_skills", []))
            data["tech_stack"] = normalize_skills(data.get("tech_stack", []))
            return JobEnrichmentOutput(**data)
        except Exception as e:
            logger.warning("ai_enrich_job_fallback", error=str(e))
            req_s, pref_s = extract_skills_from_text(description, title=title)
            return JobEnrichmentOutput(
                standardized_title=norm_title,
                role_category=inferred_cat,
                seniority="ENTRY_LEVEL" if (min_exp or 0) <= 1 else "MID",
                min_experience_years=min_exp,
                max_experience_years=max_exp,
                required_skills=req_s,
                preferred_skills=pref_s,
                core_responsibilities=["Develop and maintain software solutions."],
                requirements_summary=[f"Experience with {', '.join(req_s[:4])}"] if req_s else [],
                tech_stack=req_s[:6],
                remote_policy_reasoning="Derived from job posting details via fallback.",
            )

    async def generate_why_this_job(
        self,
        job_id: str,
        job_title: str,
        company_name: str,
        match_breakdown: dict[str, Any],
        candidate_years: float = 0.0,
        job_exp_min: float | None = None,
        job_exp_max: float | None = None,
        job_location: str = "India",
        job_remote_type: str | None = None,
        candidate_preferred_locations: list[str] | None = None,
        candidate_remote_allowed: bool = True,
        use_llm: bool = True,
    ) -> WhyThisJobResponse:
        """Phase 45: Builds deterministic 'Why This Job?' evidence breakdown with LLM synthesis."""
        overall_score = float(match_breakdown.get("overall_score", 0.0))
        recommendation = str(match_breakdown.get("recommendation", "SKIP"))
        
        # Determine verdict: APPLY (>=65), CONSIDER (50-64.9), SKIP (<50)
        if overall_score >= 65.0:
            verdict = "APPLY"
        elif overall_score >= 50.0:
            verdict = "CONSIDER"
        else:
            verdict = "SKIP"

        req_info = match_breakdown.get("required_skills") or {}
        pref_info = match_breakdown.get("preferred_skills") or {}
        strong_matches = req_info.get("matched", [])
        missing_critical = req_info.get("missing", [])
        missing_nice_to_have = pref_info.get("missing", [])

        # Format transferable details
        raw_trans = match_breakdown.get("transferable_details") or []
        transferable_matches: list[TransferableMatchItem] = []
        for t in raw_trans:
            c_skill = t.get("candidate_skill", "")
            j_skill = t.get("job_skill", "")
            credit = float(t.get("credit", 0.5))
            transferable_matches.append(
                TransferableMatchItem(
                    job_skill=j_skill,
                    candidate_skill=c_skill,
                    rationale=f"Candidate's {c_skill} maps directly ({int(credit * 100)}% credit) to target {j_skill}",
                    credit=credit,
                )
            )

        # Experience Status
        exp_eligible = bool(match_breakdown.get("experience_eligible", True))
        if job_exp_min is not None and job_exp_max is not None:
            exp_text = f"Required: {job_exp_min}–{job_exp_max} years | Profile: {candidate_years:.1f} years"
        elif job_exp_min is not None:
            exp_text = f"Required: {job_exp_min}+ years | Profile: {candidate_years:.1f} years"
        else:
            exp_text = f"Required: Unspecified | Profile: {candidate_years:.1f} years"
        
        if not exp_eligible:
            exp_summary = f"Experience mismatch: {exp_text}"
        else:
            exp_summary = f"Experience eligible: {exp_text}"

        exp_status = ExperienceStatus(
            eligible=exp_eligible,
            candidate_years=candidate_years,
            required_min=job_exp_min,
            required_max=job_exp_max,
            summary=exp_summary,
        )

        # Location Status
        loc_eligible = bool(match_breakdown.get("location_eligible", True))
        remote_str = (job_remote_type or "ONSITE").upper()
        if remote_str == "REMOTE":
            loc_summary = "Remote role matches flexible preference"
        elif loc_eligible:
            loc_summary = f"Location '{job_location}' matches preferred target cities"
        else:
            loc_summary = f"Location '{job_location}' outside preferred locations and not remote"

        loc_status = LocationStatus(
            eligible=loc_eligible,
            job_location=job_location,
            remote_type=job_remote_type,
            candidate_locations=candidate_preferred_locations or [],
            remote_allowed=candidate_remote_allowed,
            summary=loc_summary,
        )

        # Build Rejection / Warning reasons
        rejection_reasons: list[str] = []
        if missing_critical:
            rejection_reasons.append(f"Missing required skills: {', '.join(missing_critical[:4])}")
        if not exp_eligible:
            rejection_reasons.append(exp_summary)
        if not loc_eligible:
            rejection_reasons.append(loc_summary)

        # Deterministic Baseline Headline & Recommendation
        if verdict == "APPLY":
            headline = f"Strong Match ({overall_score:.0f}%) — Core Requirements Met"
            recommendation_text = (
                f"Strong match. Your background in {', '.join(strong_matches[:3]) or 'required stack'} "
                f"aligns directly with {company_name}. Direct manual application recommended."
            )
            talking_points = [
                f"Highlight proven production experience in {s}." for s in strong_matches[:3]
            ]
            if transferable_matches:
                talking_points.append(
                    f"Frame adjacent work with {transferable_matches[0].candidate_skill} to fulfill {transferable_matches[0].job_skill}."
                )
        elif verdict == "CONSIDER":
            headline = f"Potential Match ({overall_score:.0f}%) — Bridgeable Skill Gap"
            recommendation_text = (
                f"Consider applying. You possess key transferable skills, though {', '.join(missing_critical[:2]) or 'some requirements'} "
                f"are missing. Emphasize adjacent stack experience."
            )
            talking_points = [
                f"Emphasize strong fundamentals in {', '.join(strong_matches[:2]) or 'your core stack'}."
            ]
            if transferable_matches:
                talking_points.append(
                    f"Explain how {transferable_matches[0].candidate_skill} experience translates to {transferable_matches[0].job_skill}."
                )
        else:
            headline = f"Low Compatibility ({overall_score:.0f}%) — Key Mismatches"
            recommendation_text = (
                f"Skip. Significant gaps in core requirements ({', '.join(missing_critical[:3]) or 'experience/stack'}). "
                f"Focus on higher-affinity roles."
            )
            talking_points = []

        is_llm_generated = False
        # Optional LLM Enhancement for natural narrative
        if use_llm:
            prompt = f"""You are an objective AI career copilot. Explain why the candidate should apply or skip this job.
Job: {job_title} at {company_name}
Match Score: {overall_score}% ({recommendation})
Verdict: {verdict}
Matched Skills: {', '.join(strong_matches[:6]) if strong_matches else 'None'}
Missing Critical Skills: {', '.join(missing_critical[:4]) if missing_critical else 'None'}
Transferable: {', '.join([f"{t.candidate_skill}->{t.job_skill}" for t in transferable_matches]) if transferable_matches else 'None'}
Experience: {exp_summary}
Location: {loc_summary}

Respond in valid JSON:
{{
  "headline": "Punchy 4-7 word headline",
  "recommendation_text": "Crisp 2-sentence candid reasoning on applying or skipping",
  "interview_talking_points": ["point 1", "point 2"]
}}"""
            messages = [
                {"role": "system", "content": "You are a concise, objective AI tech hiring advisor. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ]
            try:
                llm_res = await self.provider.complete_json(messages)
                if llm_res.get("headline"):
                    headline = str(llm_res["headline"]).strip()
                if llm_res.get("recommendation_text"):
                    recommendation_text = str(llm_res["recommendation_text"]).strip()
                if llm_res.get("interview_talking_points") and isinstance(llm_res["interview_talking_points"], list):
                    talking_points = [str(p) for p in llm_res["interview_talking_points"] if p]
                is_llm_generated = True
            except Exception as e:
                logger.warning("why_this_job_llm_enrichment_failed", job_id=job_id, error=str(e))

        return WhyThisJobResponse(
            job_id=job_id,
            job_title=job_title,
            company_name=company_name,
            overall_score=overall_score,
            verdict=verdict,
            recommendation=recommendation,
            headline=headline,
            strong_matches=strong_matches,
            transferable_matches=transferable_matches,
            missing_critical=missing_critical,
            missing_nice_to_have=missing_nice_to_have,
            experience_status=exp_status,
            location_status=loc_status,
            recommendation_text=recommendation_text,
            rejection_reasons=rejection_reasons,
            interview_talking_points=talking_points,
            confidence=float(match_breakdown.get("confidence", 1.0)),
            confidence_label=str(match_breakdown.get("confidence_label", "HIGH")),
            is_llm_generated=is_llm_generated,
        )

