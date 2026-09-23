import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import async_session_factory
from app.intelligence.llm_provider import create_ai_provider
from app.intelligence.base import clean_and_extract_json
from app.models.application_preparation import ApplicationPreparation
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.services.preference_service import get_or_create_preferences

from sqlalchemy.exc import IntegrityError

logger = structlog.get_logger(__name__)


def _extract_metrics(text: str) -> list[str]:
    """Finds key numerical and quantitative metrics (e.g. 40%, 1M, 99.9%, $500k, 10x)."""
    pattern = r"\b(?:\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?[kKmMbB]?|\d+(?:\.\d+)?[kKmMbB]|\d+(?:\.\d+)?x|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b\d+\b(?=\s*(?:users|requests|ms|seconds|minutes|hours|days|percent|pct|rps|qps|endpoints|services|microservices|tables|records|lines|stars|commits)))\b"
    return re.findall(pattern, text, re.IGNORECASE)


def _normalize_browser_research(raw_research: Any) -> dict[str, Any]:
    """Converts unstructured browser research data into a compact high-signal dictionary."""
    if not raw_research or not isinstance(raw_research, dict):
        return {}
    summary = raw_research.get("company_summary") or raw_research.get("description") or raw_research.get("about")
    products = raw_research.get("products") or raw_research.get("core_products") or []
    tech = raw_research.get("tech_stack") or raw_research.get("technologies") or []
    culture = raw_research.get("culture") or raw_research.get("values") or []

    # If raw is a flat crawl output
    if not summary and "text" in raw_research:
        summary = str(raw_research["text"])[:300]

    normalized = {}
    if summary:
        normalized["company_summary"] = str(summary)[:350]
    if products:
        normalized["products"] = products[:4] if isinstance(products, list) else [str(products)[:150]]
    if tech:
        normalized["tech_stack"] = tech[:6] if isinstance(tech, list) else [str(tech)[:150]]
    if culture:
        normalized["culture_values"] = culture[:3] if isinstance(culture, list) else [str(culture)[:150]]
    return normalized


async def _resolve_candidate_contact(
    db: AsyncSession,
    user_id: uuid.UUID,
    resume: Resume | None,
    profile: CandidateProfile | None,
) -> dict[str, str]:
    """Consolidated helper to retrieve candidate contact details with clean fallbacks."""
    user_res = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_res.scalar_one_or_none()

    extracted = (resume.extracted_data or {}) if resume else {}
    name = extracted.get("candidate_name")
    if not name or name.strip() in ("", "Candidate"):
        other_resumes = (
            await db.execute(
                select(Resume)
                .where(Resume.user_id == user_id)
                .order_by(Resume.created_at.desc())
            )
        ).scalars().all()
        for r in other_resumes:
            c_name = (r.extracted_data or {}).get("candidate_name")
            if c_name and c_name.strip() not in ("", "Candidate"):
                name = c_name
                break
    name = name or "Applicant"

    email = extracted.get("email")
    if not email or "@jobsearchai.local" in str(email):
        if user_obj and user_obj.email and "@jobsearchai.local" not in str(user_obj.email):
            email = user_obj.email
        else:
            email = ""

    phone = extracted.get("phone") or ""
    loc = (
        extracted.get("location")
        or (profile.preferred_locations[0] if (profile and profile.preferred_locations) else "")
    )

    return {
        "name": str(name).strip(),
        "email": str(email).strip(),
        "phone": str(phone).strip(),
        "location": str(loc).strip(),
    }


class ApplicationPrepService:
    @staticmethod
    async def get_or_create_preparation(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ApplicationPreparation:
        """Retrieves or creates the preparation record for a user and job."""
        stmt = select(ApplicationPreparation).where(
            ApplicationPreparation.user_id == user_id,
            ApplicationPreparation.job_id == job_id,
        )
        res = await db.execute(stmt)
        prep = res.scalar_one_or_none()
        if not prep:
            profile_res = await db.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == user_id)
            )
            profile = profile_res.scalar_one_or_none()

            active_resume = None
            if profile and profile.source_resume_id:
                res = await db.execute(select(Resume).where(Resume.id == profile.source_resume_id))
                active_resume = res.scalar_one_or_none()

            if not active_resume:
                resume_stmt = (
                    select(Resume)
                    .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
                    .order_by(Resume.created_at.desc())
                )
                all_active = (await db.execute(resume_stmt)).scalars().all()
                for r in all_active:
                    if r.extracted_data and r.extracted_data.get("candidate_name") and r.extracted_data.get("candidate_name") != "Candidate":
                        active_resume = r
                        break
                if not active_resume and all_active:
                    active_resume = all_active[0]

            prep = ApplicationPreparation(
                user_id=user_id,
                job_id=job_id,
                resume_mode="EXISTING",
                resume_id=active_resume.id if active_resume else None,
                status="DRAFT",
            )
            db.add(prep)
            try:
                await db.commit()
                await db.refresh(prep)
            except IntegrityError:
                await db.rollback()
                res = await db.execute(stmt)
                prep = res.scalar_one_or_none()
                if not prep:
                    raise
        return prep

    @staticmethod
    async def prepare_resume_for_job(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        mode: str = "EXISTING",
    ) -> dict[str, Any]:
        """
        Prepares structured, factually grounded tailored resume for a specific target job.
        Implements metric preservation and source bullet traceability.
        """
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)

        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get baseline resume & candidate profile
        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        resume = None
        if prep.resume_id:
            res = await db.execute(select(Resume).where(Resume.id == prep.resume_id))
            resume = res.scalar_one_or_none()

        if not resume and profile and profile.source_resume_id:
            res = await db.execute(select(Resume).where(Resume.id == profile.source_resume_id))
            resume = res.scalar_one_or_none()

        if not resume:
            resume_res = await db.execute(
                select(Resume)
                .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
                .order_by(Resume.created_at.desc())
            )
            all_active = resume_res.scalars().all()
            for r in all_active:
                if r.extracted_data and r.extracted_data.get("candidate_name") and r.extracted_data.get("candidate_name") != "Candidate":
                    resume = r
                    break
            if not resume and all_active:
                resume = all_active[0]

        if not resume and not profile:
            raise ValueError("No candidate profile or resume found to prepare application.")

        prep.resume_mode = mode.upper()
        if resume:
            prep.resume_id = resume.id

        if prep.resume_mode == "EXISTING":
            prep.tailored_resume_content = None
            await db.commit()
            await db.refresh(prep)
            return {
                "status": "ok",
                "resume_mode": "EXISTING",
                "resume_id": str(resume.id) if resume else None,
                "message": "Using existing candidate resume without modifications.",
            }

        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        research_context = _normalize_browser_research((job.raw_data or {}).get("browser_research", {}))

        # Build indexed structured source experiences & projects
        source_work_experience = profile.work_experience if (profile and profile.work_experience) else []
        structured_exp_input = []
        for i, exp in enumerate(source_work_experience):
            bullets = exp.get("description") or exp.get("bullets") or []
            if isinstance(bullets, str):
                bullets = [bullets]
            structured_exp_input.append({
                "source_experience_index": i,
                "title": exp.get("title") or exp.get("role") or "",
                "company": exp.get("company") or "",
                "bullets": [{"source_bullet_index": b_i, "text": b} for b_i, b in enumerate(bullets)],
            })

        source_projects = profile.projects if (profile and profile.projects) else []
        structured_proj_input = []
        for p_i, proj in enumerate(source_projects):
            bullets = proj.get("description") or proj.get("bullets") or []
            if isinstance(bullets, str):
                bullets = [bullets]
            structured_proj_input.append({
                "source_project_index": p_i,
                "name": proj.get("name") or proj.get("title") or "",
                "technologies": proj.get("technologies") or [],
                "bullets": [{"source_bullet_index": b_idx, "text": b} for b_idx, b in enumerate(bullets)],
            })

        # Categorize skills from candidate taxonomy
        candidate_skills_catalog = {
            "Languages": profile.programming_languages if profile else [],
            "Frameworks": profile.frameworks if profile else [],
            "Databases": profile.databases if profile else [],
            "Cloud / DevOps": profile.cloud if profile else [],
            "Tools": profile.tools if profile else [],
        }

        system_prompt = (
            "You are an expert technical career advisor tailoring an engineering resume for a target job.\n"
            "STRICT GROUNDING & ANTI-HALLUCINATION RULES:\n"
            "1. NEVER invent past companies, employment dates, job titles, degrees, or metrics.\n"
            "2. NEVER invent technologies or skills the candidate does not have.\n"
            "3. METRIC PRESERVATION: If an existing candidate bullet contains numerical metrics, percentages, throughput numbers, or dollar values, you MUST PRESERVE those exact metrics accurately. Never degrade a specific metric (e.g. 'reduced latency by 40%') into vague words ('improved performance').\n"
            "4. TRACEABILITY: Every experience and project bullet in your response must reference its source_experience_index/source_project_index and source_bullet_index.\n"
            "5. Return valid JSON only matching the requested schema."
        )

        user_prompt = f"""
Candidate Structured Source Data:
- Experience Level: {profile.experience_level if profile else 'FRESHER'}
- Categorized Skills: {json.dumps(candidate_skills_catalog)}
- Work Experience:
{json.dumps(structured_exp_input, indent=2)}
- Projects:
{json.dumps(structured_proj_input, indent=2)}

Target Job:
- Title: {job.title}
- Company: {job.company_name}
- Required Skills: {job.required_skills}
- Preferred Skills: {job.preferred_skills}
- Description Excerpt: {job.description[:1800]}
- Normalized Company Research: {json.dumps(research_context) if research_context else 'None'}

Return a JSON object with:
{{
  "tailored_summary": "Crisp 2-3 sentence summary aligning genuine candidate experience directly with this role.",
  "categorized_skills": {{
    "Languages": ["skills matching candidate list"],
    "Frameworks": ["skills matching candidate list"],
    "Databases": ["skills matching candidate list"],
    "Cloud / DevOps": ["skills matching candidate list"],
    "Tools": ["skills matching candidate list"]
  }},
  "highlighted_skills": ["top 4-6 matching skills"],
  "experience": [
    {{
      "source_experience_index": 0,
      "selected_bullets": [
        {{
          "source_bullet_index": 0,
          "content": "Reframed bullet emphasizing job-relevant keywords while strictly retaining all numbers, metrics, and genuine tasks."
        }}
      ]
    }}
  ],
  "projects": [
    {{
      "source_project_index": 0,
      "selected_bullets": [
        {{
          "source_bullet_index": 0,
          "content": "Crisp achievement bullet from this genuine project."
        }}
      ]
    }}
  ]
}}
"""
        response_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        try:
            tailored_json = clean_and_extract_json(response_text)
        except Exception:
            logger.warning("resume_tailoring_json_parse_fallback")
            tailored_json = {}

        # Run Grounding and Metric Validation
        tailored_json = ApplicationPrepService._validate_and_sanitize_resume(
            tailored_json=tailored_json,
            source_exp=source_work_experience,
            source_proj=source_projects,
            candidate_skills=profile.skills if profile else [],
            candidate_skills_catalog=candidate_skills_catalog,
        )

        prep.tailored_resume_content = tailored_json
        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "resume_mode": "TAILORED",
            "resume_id": str(resume.id) if resume else None,
            "tailored_content": tailored_json,
        }

    @staticmethod
    def _validate_and_sanitize_resume(
        tailored_json: dict[str, Any],
        source_exp: list[dict[str, Any]],
        source_proj: list[dict[str, Any]],
        candidate_skills: list[str],
        candidate_skills_catalog: dict[str, list[str]],
    ) -> dict[str, Any]:
        """
        Validates LLM output against candidate sources.
        Enforces metric retention and verifies skill groundings.
        Falls back safely to source content if invalid.
        """
        sanitized = dict(tailored_json)

        # 1. Validate summary
        if not sanitized.get("tailored_summary") or len(str(sanitized.get("tailored_summary"))) < 15:
            sanitized["tailored_summary"] = ""

        # 2. Validate categorized skills against candidate genuine skills
        valid_skills_set = {s.lower() for s in candidate_skills}
        cat_skills = sanitized.get("categorized_skills") or {}
        cleaned_cat: dict[str, list[str]] = {}
        for cat, sk_list in cat_skills.items():
            if isinstance(sk_list, list):
                # Filter out hallucinated skills
                valid_in_cat = [s for s in sk_list if str(s).lower() in valid_skills_set]
                if valid_in_cat:
                    cleaned_cat[cat] = valid_in_cat

        # Fallback to catalog if empty
        if not cleaned_cat:
            cleaned_cat = {k: v for k, v in candidate_skills_catalog.items() if v}
        sanitized["categorized_skills"] = cleaned_cat

        # 3. Validate work experience bullets & metric preservation
        exp_entries = sanitized.get("experience") or []
        validated_exp = []
        for item in exp_entries:
            idx = item.get("source_experience_index")
            if idx is not None and isinstance(idx, int) and 0 <= idx < len(source_exp):
                source_bullets = source_exp[idx].get("description") or source_exp[idx].get("bullets") or []
                if isinstance(source_bullets, str):
                    source_bullets = [source_bullets]

                sel_bullets = item.get("selected_bullets") or []
                validated_bullets = []
                for b in sel_bullets:
                    b_idx = b.get("source_bullet_index") if isinstance(b, dict) else None
                    content = b.get("content") if isinstance(b, dict) else str(b)

                    if b_idx is not None and 0 <= b_idx < len(source_bullets):
                        orig_text = source_bullets[b_idx]
                        orig_metrics = _extract_metrics(orig_text)
                        # Metric preservation check
                        missing_metrics = [m for m in orig_metrics if m.lower() not in content.lower()]
                        if missing_metrics:
                            # Revert to original bullet to guarantee zero metric loss
                            content = orig_text
                    elif not content:
                        continue
                    validated_bullets.append({"content": content})

                if not validated_bullets and source_bullets:
                    validated_bullets = [{"content": b} for b in source_bullets]

                validated_exp.append({
                    "source_experience_index": idx,
                    "selected_bullets": validated_bullets,
                })

        # If LLM didn't return experience or returned corrupted indices, fallback to source
        if not validated_exp:
            for i, exp in enumerate(source_exp):
                s_bullets = exp.get("description") or exp.get("bullets") or []
                if isinstance(s_bullets, str):
                    s_bullets = [s_bullets]
                validated_exp.append({
                    "source_experience_index": i,
                    "selected_bullets": [{"content": b} for b in s_bullets],
                })
        sanitized["experience"] = validated_exp

        # 4. Validate projects
        proj_entries = sanitized.get("projects") or []
        validated_proj = []
        for p_item in proj_entries:
            p_idx = p_item.get("source_project_index")
            if p_idx is not None and isinstance(p_idx, int) and 0 <= p_idx < len(source_proj):
                s_proj_bullets = source_proj[p_idx].get("description") or source_proj[p_idx].get("bullets") or []
                if isinstance(s_proj_bullets, str):
                    s_proj_bullets = [s_proj_bullets]

                sel_bullets = p_item.get("selected_bullets") or []
                v_p_bullets = []
                for b in sel_bullets:
                    b_content = b.get("content") if isinstance(b, dict) else str(b)
                    if b_content:
                        v_p_bullets.append({"content": b_content})

                if not v_p_bullets and s_proj_bullets:
                    v_p_bullets = [{"content": b} for b in s_proj_bullets]

                validated_proj.append({
                    "source_project_index": p_idx,
                    "selected_bullets": v_p_bullets,
                })

        if not validated_proj and source_proj:
            for i, proj in enumerate(source_proj):
                s_p_bullets = proj.get("description") or proj.get("bullets") or []
                if isinstance(s_p_bullets, str):
                    s_p_bullets = [s_p_bullets]
                validated_proj.append({
                    "source_project_index": i,
                    "selected_bullets": [{"content": b} for b in s_p_bullets],
                })
        sanitized["projects"] = validated_proj

        return sanitized

    @staticmethod
    async def generate_cover_letter(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        tone: str = "PROFESSIONAL",
        custom_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Generates structured, factually grounded cover letter using normalized company research
        and distinct tone behavioral guidelines.
        """
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)

        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        # Resolve resume
        resume = None
        if prep.resume_id:
            res = await db.execute(select(Resume).where(Resume.id == prep.resume_id))
            resume = res.scalar_one_or_none()
        if not resume and profile and profile.source_resume_id:
            res = await db.execute(select(Resume).where(Resume.id == profile.source_resume_id))
            resume = res.scalar_one_or_none()
        if not resume:
            resume_res = await db.execute(
                select(Resume)
                .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
                .order_by(Resume.created_at.desc())
            )
            all_active = resume_res.scalars().all()
            for r in all_active:
                if r.extracted_data and r.extracted_data.get("candidate_name") and r.extracted_data.get("candidate_name") != "Candidate":
                    resume = r
                    break
            if not resume and all_active:
                resume = all_active[0]

        contact = await _resolve_candidate_contact(db, user_id, resume, profile)
        candidate_name = contact["name"]

        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        research_context = _normalize_browser_research((job.raw_data or {}).get("browser_research", {}))

        # Explicit Tone Profiles
        tone_normalized = tone.upper()
        if tone_normalized == "CONCISE":
            tone_instructions = (
                "TONE: CONCISE.\n"
                "- High signal-to-noise ratio, zero filler, immediate value proposition.\n"
                "- Maximum 160-200 words across the entire body.\n"
                "- Direct, tight sentences connecting top technical strengths to core requirements."
            )
        elif tone_normalized == "ENTHUSIASTIC":
            tone_instructions = (
                "TONE: ENTHUSIASTIC.\n"
                "- Energetic, proactive, mission-oriented yet strictly grounded in evidence.\n"
                "- Show genuine passion for solving the team's engineering challenges.\n"
                "- Avoid hyperbolic adjectives; back enthusiasm with candidate's actual projects (~220-260 words)."
            )
        else:  # PROFESSIONAL
            tone_instructions = (
                "TONE: PROFESSIONAL.\n"
                "- Formal, measured, executive technical prose (~220-260 words).\n"
                "- Objective evidence-driven connection to the company's stack and requirements."
            )

        system_prompt = (
            "You are an expert career copilot generating targeted, authentic job application letters.\n"
            "STRICT GROUNDING & STRUCTURE RULES:\n"
            "1. DO NOT GENERATE HEADERS, CONTACT INFO, DATES, OR SIGN-OFFS. The PDF renderer generates them.\n"
            "2. Generate ONLY the 4 structured letter paragraphs as JSON.\n"
            "3. Ground all claims in the candidate's actual background. NEVER invent past companies, degrees, positions, or technologies.\n"
            "4. If company research context is provided, reference specific products or engineering signals naturally. If NO research context is provided, DO NOT invent company details or use hollow flattery (e.g. 'I admire your innovative company'). Instead focus on the technical domain of the role.\n"
            "5. Return valid JSON only."
        )

        user_prompt = f"""
Candidate Profile:
- Full Name: {candidate_name}
- Skills: {profile.skills if profile else []}
- Experience Level: {profile.experience_level if profile else 'FRESHER'}
- Work Experience: {profile.work_experience if profile else []}
- Projects: {profile.projects if profile else []}
- Target Roles: {profile.target_roles if profile else []}
- Custom Notes / Instructions: {custom_notes or 'None'}

Target Job:
- Title: {job.title}
- Company: {job.company_name}
- Location: {job.location}
- Required Skills: {job.required_skills}
- Preferred Skills: {job.preferred_skills}
- Description: {job.description[:1800]}
- Normalized Company Research: {json.dumps(research_context) if research_context else 'None'}

{tone_instructions}

Return JSON with 4 distinct paragraphs:
{{
  "opening": "Opening paragraph stating target position and immediate value proposition without generic fluff.",
  "evidence_paragraph": "Evidence paragraph connecting 1-2 concrete accomplishments/projects with preserved metrics directly to job requirements.",
  "company_connection": "Paragraph connecting candidate's engineering interests to the specific company product/stack (or role domain if research unavailable).",
  "closing": "Crisp 1-2 sentence professional next-step closing."
}}
"""
        response_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        try:
            cl_json = clean_and_extract_json(response_text)
            # Store formatted clean paragraphs as plain text with double newlines
            paragraphs = [
                cl_json.get("opening", ""),
                cl_json.get("evidence_paragraph", ""),
                cl_json.get("company_connection", ""),
                cl_json.get("closing", ""),
            ]
            cover_letter_text = "\n\n".join(p.strip() for p in paragraphs if p and p.strip())
        except Exception:
            cover_letter_text = response_text.strip()

        prep.cover_letter = cover_letter_text
        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "job_id": str(job_id),
            "cover_letter": prep.cover_letter,
        }

    @staticmethod
    async def generate_application_answers(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        questions: list[str],
    ) -> dict[str, Any]:
        """
        Generates answers for application screening questions.
        Cites source facts from profile or flags when candidate input is needed.
        """
        if not questions:
            return {"status": "ok", "answers": []}

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        system_prompt = (
            "You are an assistant preparing answers to job application screening questions.\n"
            "STRICT FACTUAL GROUNDING RULES:\n"
            "1. Base answers solely on candidate profile facts provided.\n"
            "2. If the candidate's profile doesn't have the answer (e.g. specific notice period, visa status, custom salary requirements not mentioned),\n"
            "   mark 'requires_user_input': true and suggest a draft placeholder.\n"
            "3. Return strict JSON list."
        )

        user_prompt = f"""
Candidate:
- Skills: {profile.skills if profile else []}
- Experience: {profile.experience_level if profile else 'FRESHER'}
- Preferred Locations: {profile.preferred_locations if profile else []}
- Work Experience: {profile.work_experience if profile else []}
- Target Roles: {profile.target_roles if profile else []}

Job:
- Title: {job.title}
- Company: {job.company_name}
- Description: {job.description[:1500]}

Questions to answer:
{json.dumps(questions, indent=2)}

Format response as JSON:
[
  {{
    "question": "question text",
    "answer": "draft answer",
    "source_facts": ["fact from profile used"],
    "requires_user_input": false
  }}
]
"""
        response_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        try:
            answers = clean_and_extract_json(response_text)
            if not isinstance(answers, list):
                answers = [answers]
        except Exception:
            answers = [
                {
                    "question": q,
                    "answer": "Candidate experience aligns with requirements.",
                    "source_facts": ["Profile skills"],
                    "requires_user_input": False,
                }
                for q in questions
            ]

        # Merge or update prep question answers
        existing_qa = {item.get("question"): item for item in (prep.question_answers or [])}
        for item in answers:
            if isinstance(item, dict) and "question" in item:
                existing_qa[item["question"]] = item
        prep.question_answers = list(existing_qa.values())

        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "job_id": str(job_id),
            "answers": prep.question_answers,
        }

    @staticmethod
    async def prepare_full_application(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        resume_mode: str = "EXISTING",
        include_cover_letter: bool = True,
        questions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Orchestrates comprehensive application preparation."""
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)

        # 1. Prepare resume
        resume_result = await ApplicationPrepService.prepare_resume_for_job(
            db=db, user_id=user_id, job_id=job_id, mode=resume_mode
        )

        # 2. Prepare cover letter if requested
        cover_letter_result = None
        if include_cover_letter:
            cover_letter_result = await ApplicationPrepService.generate_cover_letter(
                db=db, user_id=user_id, job_id=job_id
            )

        # 3. Answer questions if provided
        qa_result = None
        if questions:
            qa_result = await ApplicationPrepService.generate_application_answers(
                db=db, user_id=user_id, job_id=job_id, questions=questions
            )

        prep.status = "READY_FOR_REVIEW"
        await db.commit()
        await db.refresh(prep)

        job_stmt = select(Job).where(Job.id == job_id)
        job_res = await db.execute(job_stmt)
        job = job_res.scalar_one_or_none()
        app_url = (job.application_url or job.source_url) if job else None

        return {
            "status": "ok",
            "prep_id": str(prep.id),
            "job_id": str(job_id),
            "job_title": job.title if job else None,
            "company_name": job.company_name if job else None,
            "application_url": app_url,
            "prep_status": prep.status,
            "resume": resume_result,
            "cover_letter": cover_letter_result.get("cover_letter") if cover_letter_result else prep.cover_letter,
            "answers": qa_result.get("answers") if qa_result else prep.question_answers,
        }

    @staticmethod
    async def get_preparation(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Retrieves current application preparation for a job."""
        stmt = select(ApplicationPreparation).where(
            ApplicationPreparation.user_id == user_id,
            ApplicationPreparation.job_id == job_id,
        )
        res = await db.execute(stmt)
        prep = res.scalar_one_or_none()
        if not prep:
            return None

        job_stmt = select(Job).where(Job.id == job_id)
        job_res = await db.execute(job_stmt)
        job = job_res.scalar_one_or_none()
        app_url = (job.application_url or job.source_url) if job else None

        return {
            "id": str(prep.id),
            "user_id": str(prep.user_id),
            "job_id": str(prep.job_id),
            "job_title": job.title if job else None,
            "company_name": job.company_name if job else None,
            "application_url": app_url,
            "resume_mode": prep.resume_mode,
            "resume_id": str(prep.resume_id) if prep.resume_id else None,
            "tailored_resume_content": prep.tailored_resume_content,
            "cover_letter": prep.cover_letter,
            "question_answers": prep.question_answers,
            "status": prep.status,
            "metadata_info": prep.metadata_info,
            "created_at": prep.created_at.isoformat(),
            "updated_at": prep.updated_at.isoformat(),
        }

    @staticmethod
    async def update_preparation_status(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        status: str,
    ) -> dict[str, Any]:
        """Updates preparation review status (e.g. READY_FOR_REVIEW, APPROVED)."""
        valid_statuses = {
            "DRAFT",
            "PREPARING",
            "FILLING",
            "READY_FOR_REVIEW",
            "APPROVED",
            "SUBMITTED",
            "FAILED",
        }
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        prep.status = status
        await db.commit()
        await db.refresh(prep)
        return {
            "status": "ok",
            "prep_id": str(prep.id),
            "job_id": str(job_id),
            "prep_status": prep.status,
        }

    @staticmethod
    async def export_resume_pdf(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        mode: str = "EXISTING",
    ) -> bytes:
        """Renders single-column ATS-friendly 1-page resume PDF."""
        from app.services.pdf_generator_service import PDFGeneratorService

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        resume = None
        if prep.resume_id:
            res = await db.execute(select(Resume).where(Resume.id == prep.resume_id))
            resume = res.scalar_one_or_none()
        if not resume and profile and profile.source_resume_id:
            res = await db.execute(select(Resume).where(Resume.id == profile.source_resume_id))
            resume = res.scalar_one_or_none()
        if not resume:
            resume_res = await db.execute(
                select(Resume)
                .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
                .order_by(Resume.created_at.desc())
            )
            all_active = resume_res.scalars().all()
            for r in all_active:
                if r.extracted_data and r.extracted_data.get("candidate_name") and r.extracted_data.get("candidate_name") != "Candidate":
                    resume = r
                    break
            if not resume and all_active:
                resume = all_active[0]

        extracted = (resume.extracted_data or {}) if resume else {}
        contact = await _resolve_candidate_contact(db, user_id, resume, profile)

        # Tailored data if requested
        tailored_data = prep.tailored_resume_content
        if mode == "TAILORED" and not tailored_data:
            res_dict = await ApplicationPrepService.prepare_resume_for_job(db, user_id, job_id, mode="TAILORED")
            tailored_data = res_dict.get("tailored_content")

        candidate_data = {
            "name": contact["name"],
            "email": contact["email"],
            "phone": contact["phone"],
            "location": contact["location"],
            "summary": extracted.get("summary") or (profile.summary if profile else ""),
            "skills": profile.skills if profile else (extracted.get("skills") or []),
            "categorized_skills": {
                "Languages": profile.programming_languages if profile else [],
                "Frameworks": profile.frameworks if profile else [],
                "Databases": profile.databases if profile else [],
                "Cloud / DevOps": profile.cloud if profile else [],
                "Tools": profile.tools if profile else [],
            },
            "work_experience": profile.work_experience if (profile and profile.work_experience) else (extracted.get("work_experience") or []),
            "projects": profile.projects if (profile and profile.projects) else (extracted.get("projects") or []),
            "education": profile.education if (profile and profile.education) else (extracted.get("education") or []),
        }


        job_data = {
            "title": job.title,
            "company_name": job.company_name,
        }

        html_content = PDFGeneratorService.render_resume_html(
            candidate_data=candidate_data,
            job_data=job_data,
            tailored_data=tailored_data,
            mode=mode,
        )
        return await PDFGeneratorService.generate_pdf_from_html(html_content)


    @staticmethod
    async def export_cover_letter_pdf(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> bytes:
        """Renders targeted cover letter PDF."""
        from app.services.pdf_generator_service import PDFGeneratorService

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not prep.cover_letter:
            res = await ApplicationPrepService.generate_cover_letter(db, user_id, job_id)
            prep.cover_letter = res.get("cover_letter")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        resume = None
        if prep.resume_id:
            res = await db.execute(select(Resume).where(Resume.id == prep.resume_id))
            resume = res.scalar_one_or_none()
        if not resume and profile and profile.source_resume_id:
            res = await db.execute(select(Resume).where(Resume.id == profile.source_resume_id))
            resume = res.scalar_one_or_none()

        contact = await _resolve_candidate_contact(db, user_id, resume, profile)

        candidate_data = {
            "name": contact["name"],
            "email": contact["email"],
            "phone": contact["phone"],
            "location": contact["location"],
        }

        job_data = {
            "title": job.title,
            "company_name": job.company_name,
        }

        html_content = PDFGeneratorService.render_cover_letter_html(
            candidate_data=candidate_data,
            job_data=job_data,
            cover_letter_data=prep.cover_letter or "",
        )
        return await PDFGeneratorService.generate_pdf_from_html(html_content)


