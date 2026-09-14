import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence
import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.preference import Preference
from app.utils.normalization import normalize_skill, normalize_skills

logger = structlog.get_logger(__name__)

# Directional Transferable Skills Taxonomy with explicit credit weighting:
# candidate_skill -> {job_skill: credit} (0.5 for strong, 0.2-0.4 for moderate/weak)
TRANSFERABLE_TAXONOMY: dict[str, dict[str, float]] = {
    "python": {
        "fastapi": 0.5,
        "flask": 0.5,
        "django": 0.5,
        "pytorch": 0.3,
        "scikit-learn": 0.3,
    },
    "fastapi": {
        "flask": 0.5,
        "django": 0.4,
        "rest apis": 0.8,
        "pydantic": 0.8,
        "python": 0.5,
    },
    "javascript": {
        "typescript": 0.5,
        "node.js": 0.5,
        "html": 0.5,
        "css": 0.5,
    },
    "typescript": {
        "javascript": 0.9,
        "node.js": 0.5,
        "react": 0.5,
    },
    "react": {
        "next.js": 0.6,
        "vite": 0.5,
        "vue.js": 0.3,
        "redux": 0.5,
    },
    "next.js": {
        "react": 0.8,
    },
    "node.js": {
        "express.js": 0.7,
        "rest apis": 0.7,
        "javascript": 0.8,
    },
    "express.js": {
        "node.js": 0.7,
        "rest apis": 0.8,
    },
    "postgresql": {
        "mysql": 0.5,
        "sqlite": 0.5,
        "sql": 0.9,
    },
    "mysql": {
        "postgresql": 0.5,
        "sqlite": 0.5,
        "sql": 0.9,
    },
    "docker": {
        "kubernetes": 0.3,
    },
    "pytorch": {
        "tensorflow": 0.5,
        "deep learning": 0.6,
        "python": 0.5,
    },
    "machine learning": {
        "deep learning": 0.5,
        "nlp": 0.4,
        "data science": 0.5,
    },
    "llm": {
        "rag": 0.6,
        "langchain": 0.5,
        "prompt engineering": 0.7,
    },
    "rag": {
        "llm": 0.5,
        "vector search": 0.7,
        "pgvector": 0.7,
    },
    "java": {
        "spring boot": 0.5,
    },
    "spring boot": {
        "java": 0.8,
    },
}

# Backwards-compatibility map for existing tests/consumers
TRANSFERABLE_SKILLS_MAP: dict[str, set[str]] = {
    k: set(v.keys()) for k, v in TRANSFERABLE_TAXONOMY.items()
}


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    a = np.array(v1)
    b = np.array(v2)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


class MatchingService:
    """
    Deterministic Skill-First Matching Engine.
    Weights:
      Required Skill Match: 60%
      Preferred Skill Match: 15%
      Transferable Skill Match: 10%
      Experience Match: 5%
      Location Match: 5%
      Preference Alignment: 5%

    Job Title / Semantic similarity are excluded from the primary scoring formula
    to eliminate false-positive title and context inflation.
    Anti-inflation gating caps score if candidate lacks core required skills.
    """

    def compute_skill_compatibility(
        self,
        candidate_skills: list[str],
        required_skills: list[str],
        preferred_skills: list[str],
    ) -> dict[str, Any]:
        """
        Computes detailed required, preferred, and transferable skill compatibility.
        Distinguishes:
          - Exact match: 1.0 credit
          - Canonical/Equivalent match: 1.0 credit
          - Transferable match: 0.2 - 0.8 partial credit
          - Missing skill: 0.0 credit
        """
        # Build canonical map of candidate skills
        cand_canonical: dict[str, str] = {}
        for s in candidate_skills:
            norm = normalize_skill(s)
            cand_canonical[norm.lower()] = norm

        # Normalize required and preferred skills
        req_norm = [normalize_skill(r) for r in (required_skills or []) if r.strip()]
        pref_norm = [normalize_skill(p) for p in (preferred_skills or []) if p.strip()]

        matched_required: list[str] = []
        missing_required: list[str] = []
        transferable_details: list[dict[str, Any]] = []

        # 1. Evaluate Required Skills
        for r in req_norm:
            r_low = r.lower()
            if r_low in cand_canonical:
                # Exact or canonical match
                matched_required.append(r)
            else:
                # Check for transferable proficiency
                best_cand: str | None = None
                best_credit: float = 0.0
                for c_low, c_orig in cand_canonical.items():
                    if c_low in TRANSFERABLE_TAXONOMY and r_low in TRANSFERABLE_TAXONOMY[c_low]:
                        cred = TRANSFERABLE_TAXONOMY[c_low][r_low]
                        if cred > best_credit:
                            best_credit = cred
                            best_cand = c_orig

                if best_credit > 0 and best_cand:
                    transferable_details.append({
                        "candidate_skill": best_cand,
                        "job_skill": r,
                        "credit": best_credit,
                    })
                missing_required.append(r)

        # Compute Required Skill Score (0 - 100)
        if not req_norm:
            required_score = 30.0  # Low confidence baseline when no required skills specified
        else:
            required_score = (len(matched_required) / len(req_norm)) * 100.0

        # 2. Evaluate Preferred Skills
        matched_preferred: list[str] = []
        missing_preferred: list[str] = []
        for p in pref_norm:
            p_low = p.lower()
            if p_low in cand_canonical:
                matched_preferred.append(p)
            else:
                # Also check transferable for preferred if not direct
                best_cand = None
                best_credit = 0.0
                for c_low, c_orig in cand_canonical.items():
                    if c_low in TRANSFERABLE_TAXONOMY and p_low in TRANSFERABLE_TAXONOMY[c_low]:
                        cred = TRANSFERABLE_TAXONOMY[c_low][p_low]
                        if cred > best_credit:
                            best_credit = cred
                            best_cand = c_orig
                if best_credit > 0 and best_cand:
                    transferable_details.append({
                        "candidate_skill": best_cand,
                        "job_skill": p,
                        "credit": best_credit,
                    })
                missing_preferred.append(p)

        # Compute Preferred Skill Score (0 - 100)
        # If employer listed no preferred skills, do not penalize candidate:
        # mirror required_score so candidate gets fair credit
        if not pref_norm:
            preferred_score = required_score
        else:
            preferred_score = (len(matched_preferred) / len(pref_norm)) * 100.0

        # 3. Compute Transferable Skill Score (0 - 100)
        if not req_norm or len(matched_required) == len(req_norm):
            # Candidate possesses 100% of required skills directly
            transferable_score = 100.0
        elif not missing_required and not missing_preferred:
            transferable_score = 100.0
        else:
            # Credit based on coverage of missing skills
            total_missing = len(missing_required)
            trans_credits = sum(t["credit"] for t in transferable_details if t["job_skill"] in missing_required)
            transferable_score = min(100.0, (trans_credits / total_missing) * 100.0 * 2.0)

        # Overall composite skill score (scaled 0 - 100)
        # Skills comprise 85% total: 60% req, 15% pref, 10% trans
        comp_skill_score = (
            (required_score * (0.60 / 0.85))
            + (preferred_score * (0.15 / 0.85))
            + (transferable_score * (0.10 / 0.85))
        )
        comp_skill_score = round(max(0.0, min(100.0, comp_skill_score)), 1)

        return {
            "required_score": round(required_score, 1),
            "preferred_score": round(preferred_score, 1),
            "transferable_score": round(transferable_score, 1),
            "skill_score": comp_skill_score,
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_preferred": matched_preferred,
            "missing_preferred": missing_preferred,
            "transferable_details": transferable_details,
        }

    def compute_skill_score(
        self, candidate_skills: list[str], required_skills: list[str], preferred_skills: list[str]
    ) -> tuple[float, list[str], list[str], list[str]]:
        """
        Backwards-compatible interface for legacy unit tests.
        Returns: (final_score, direct_matches, missing_skills, transferable_matches)
        """
        compat = self.compute_skill_compatibility(candidate_skills, required_skills, preferred_skills)

        # Format transferable matches as readable strings
        trans_strings = [
            f"{t['job_skill']} (via {t['candidate_skill']})"
            for t in compat["transferable_details"]
        ]

        # In legacy tests: if transferable match exists, score reflects 50% credit per transferable
        if required_skills:
            raw_legacy = (
                (len(compat["matched_required"]) * 1.0) + (len(compat["transferable_details"]) * 0.5)
            ) / len(required_skills) * 100.0
            if preferred_skills:
                pref_bonus = (len(compat["matched_preferred"]) / len(preferred_skills)) * 10.0
                raw_legacy += pref_bonus
            legacy_score = round(max(0.0, min(100.0, raw_legacy)), 1)
        else:
            legacy_score = 85.0

        return (
            legacy_score,
            compat["matched_required"],
            compat["missing_required"],
            trans_strings,
        )

    def compute_semantic_score(
        self, job_embedding: list[float] | None, profile_embedding: list[float] | None
    ) -> float:
        if job_embedding is None or profile_embedding is None:
            return 70.0  # Baseline neutral when embedding missing
        sim = cosine_similarity(job_embedding, profile_embedding)
        # Cosine similarity for bge-small typically ranges 0.4 to 0.95 for related texts
        # Map 0.3 -> 0%, 0.85+ -> 100%
        normalized = (sim - 0.3) / (0.85 - 0.3) * 100.0
        return round(max(0.0, min(100.0, normalized)), 1)

    def compute_experience_score(
        self,
        candidate_years: int,
        job_exp_min: int | None,
        job_exp_max: int | None,
        employment_type: str | None,
        internship_allowed: bool,
    ) -> float:
        if (employment_type or "").upper() == "INTERNSHIP":
            return 100.0 if internship_allowed else 30.0

        # Unspecified experience requirement -> recall-first neutral/friendly baseline
        if job_exp_min is None and job_exp_max is None:
            return 80.0

        # Fresher / 0 years logic
        if candidate_years == 0:
            if job_exp_max is not None and job_exp_max <= 1:
                return 100.0
            eff_min = job_exp_min if job_exp_min is not None else 0
            eff_max = job_exp_max if job_exp_max is not None else eff_min
            if eff_min <= 1 and eff_max <= 2:
                return 90.0
            elif eff_min <= 2:
                return 70.0
            elif eff_min <= 3:
                return 40.0
            else:
                return 10.0

        # Candidate with >0 years
        eff_min = job_exp_min if job_exp_min is not None else 0
        if job_exp_max is not None:
            if eff_min <= candidate_years <= job_exp_max:
                return 100.0
            elif candidate_years > job_exp_max:
                diff = candidate_years - job_exp_max
                return max(30.0, 100.0 - (diff * 10.0))
            else:
                diff = eff_min - candidate_years
                return max(10.0, 100.0 - (diff * 25.0))
        else:
            # Open upper bound (e.g. 2+ years)
            if candidate_years >= eff_min:
                return 100.0
            else:
                diff = eff_min - candidate_years
                return max(10.0, 100.0 - (diff * 25.0))

    def compute_role_score(
        self,
        job_title: str,
        job_category: str | None,
        target_roles: list[str],
        excluded_roles: list[str],
    ) -> tuple[float, bool]:
        """
        Informational role check and hard exclusion check.
        NOTE: role_score has 0% weight in the primary match formula.
        Hard exclusion occurs ONLY if role matches candidate's explicitly excluded roles.
        """
        title_lower = (job_title or "").lower()
        cat_lower = (job_category or "").lower()

        # Hard exclusion check
        for excl in (excluded_roles or []):
            excl_l = excl.strip().lower()
            if not excl_l:
                continue
            if excl_l in title_lower or excl_l in cat_lower:
                return 0.0, True
            tokens = [t for t in re.findall(r"\w+", excl_l) if len(t) > 1]
            if tokens and all(t in title_lower or t in cat_lower for t in tokens):
                return 0.0, True
            if "qa" in tokens and re.search(r"\bqa\b", title_lower):
                return 0.0, True

        # Target role check (informational only)
        target_lower = [r.strip().lower() for r in target_roles if r.strip()]
        for target in target_lower:
            if target in title_lower or target in cat_lower:
                return 100.0, False

        if any(cat in title_lower for cat in ["software", "developer", "engineer"]):
            return 75.0, False

        return 50.0, False

    def compute_location_score(
        self,
        job_location: str | None,
        normalized_location: str | None,
        remote_type: str | None,
        preferred_locations: list[str],
        remote_preference: bool,
    ) -> float:
        if (remote_type or "").upper() == "REMOTE" and remote_preference:
            return 100.0

        if not preferred_locations:
            return 70.0  # Neutral baseline when no preferred locations specified

        from app.core.location_taxonomy import (
            match_location_criteria,
            parse_location_entities,
        )

        # 1. Authoritative canonical criteria match (city equality, metro cluster, or remote)
        if match_location_criteria(
            job_normalized_location=normalized_location,
            job_raw_location=job_location,
            filter_locations=preferred_locations,
            job_remote_type=remote_type,
        ):
            return 100.0

        # 2. Check same-state affinity (e.g. candidate prefers Bengaluru, job is in Mysuru/Karnataka)
        job_entities = parse_location_entities(normalized_location or job_location)
        pref_entities = [e for p in preferred_locations for e in parse_location_entities(p)]

        job_states = {e.state_or_ut.lower() for e in job_entities if e.state_or_ut}
        pref_states = {e.state_or_ut.lower() for e in pref_entities if e.state_or_ut}

        if job_states and pref_states and (job_states & pref_states):
            return 80.0

        if (remote_type or "").upper() == "HYBRID":
            return 60.0

        # Major Indian tech hubs baseline
        major_hubs = {"bengaluru", "delhi ncr", "delhi", "gurugram", "noida", "mumbai", "pune", "hyderabad", "chennai"}
        job_city_names = {e.name.lower() for e in job_entities}
        if job_city_names & major_hubs:
            return 65.0

        return 40.0

    def compute_preference_score(
        self,
        company_name: str,
        salary_max: float | None,
        minimum_salary_lpa: float | None,
        priority_companies: list[str] | None,
        excluded_companies: list[str] | None,
    ) -> tuple[float, bool]:
        comp_lower = (company_name or "").strip().lower()

        # Excluded company check
        if comp_lower and any(exc.strip().lower() == comp_lower for exc in (excluded_companies or []) if exc and exc.strip()):
            return 0.0, True

        score = 80.0  # Base neutral

        # Priority company bonus
        if any(prio.strip().lower() in comp_lower for prio in (priority_companies or []) if prio and prio.strip()):
            score += 20.0

        # Salary check
        if minimum_salary_lpa is not None:
            min_inr = minimum_salary_lpa * 100000.0
            if salary_max is not None:
                if salary_max >= min_inr:
                    score += 10.0
                else:
                    score -= 30.0

        return max(0.0, min(100.0, score)), False

    def compute_confidence(
        self,
        job: Job,
        required_skills: list[str] | None,
        preferred_skills: list[str] | None,
    ) -> tuple[float, str]:
        """
        Computes match confidence score (0.0 to 1.0) and categorical label (HIGH, MEDIUM, LOW).
        Evaluates data completeness:
          - Extracted required skills count
          - Experience specificity
          - Description confidence
        """
        num_req = len(required_skills or [])
        num_pref = len(preferred_skills or [])
        total_skills = num_req + num_pref

        # Skill clarity component (0.0 - 0.50)
        if num_req >= 3:
            skill_conf = 0.50
        elif num_req >= 1:
            skill_conf = 0.35
        elif total_skills >= 1:
            skill_conf = 0.25
        else:
            skill_conf = 0.05

        # Experience clarity component (0.0 - 0.30)
        exp_conf_val = (getattr(job, "experience_confidence", None) or "LOW").upper()
        if job.experience_min is not None or job.experience_max is not None:
            if exp_conf_val == "HIGH":
                exp_conf = 0.30
            elif exp_conf_val == "MEDIUM":
                exp_conf = 0.25
            else:
                exp_conf = 0.20
        elif job.employment_type == "INTERNSHIP":
            exp_conf = 0.25
        elif exp_conf_val == "HIGH":
            exp_conf = 0.20
        elif exp_conf_val == "MEDIUM":
            exp_conf = 0.15
        else:
            exp_conf = 0.05

        # Description / Metadata clarity component (0.0 - 0.20)
        desc_conf_val = (getattr(job, "description_confidence", None) or "HIGH").upper()
        desc_len = len(getattr(job, "description", "") or "")
        if desc_conf_val == "HIGH" and desc_len >= 150:
            meta_conf = 0.20
        elif desc_len >= 80:
            meta_conf = 0.15
        else:
            meta_conf = 0.05

        raw_conf = skill_conf + exp_conf + meta_conf
        confidence = round(max(0.1, min(1.0, raw_conf)), 2)

        if confidence >= 0.75 and num_req >= 1:
            label = "HIGH"
        elif confidence >= 0.45:
            label = "MEDIUM"
        else:
            label = "LOW"

        return confidence, label

    def evaluate_job(
        self,
        job: Job,
        profile: CandidateProfile,
        preferences: Preference | None = None,
        strict_location: bool = True,
    ) -> dict[str, Any]:
        """
        Evaluates full skill-first match for a candidate profile against a job.
        Skills are the primary matching basis (85% total weight).
        Job Title is NOT used to inflate score.
        Semantic similarity cannot compensate for missing required skills.
        """
        pref_companies = preferences.priority_companies if preferences else []
        excl_companies = preferences.excluded_companies if preferences else []

        # 1. Role Hard Exclusion and Eligibility check
        role_score, is_role_excluded = self.compute_role_score(
            job.title, job.role_category, profile.target_roles, profile.excluded_roles
        )
        from app.utils.normalization import matches_target_role
        is_role_ineligible = bool(
            profile.target_roles and not matches_target_role(job.title, profile.target_roles, job.role_category)
        )

        # 2. Preference Score & Excluded Company check
        pref_score, is_comp_excluded = self.compute_preference_score(
            job.company_name,
            job.salary_max,
            profile.minimum_salary_lpa,
            pref_companies,
            excl_companies,
        )

        # 3. Hard experience exclusion check
        pref_max_exp = (
            preferences.experience_max_years
            if (preferences and preferences.experience_max_years is not None)
            else 2
        )
        from app.sources.adapters.internshala import is_senior_title

        is_exp_excluded = False
        if job.employment_type != "INTERNSHIP":
            if job.experience_min is not None and pref_max_exp is not None and job.experience_min > pref_max_exp:
                is_exp_excluded = True
            elif pref_max_exp is not None and pref_max_exp <= 2 and is_senior_title(job.title):
                is_exp_excluded = True

        # 4. Hard location exclusion check
        is_loc_excluded = False
        if strict_location and profile and profile.preferred_locations:
            pref_locs_l = [loc_item.strip().lower() for loc_item in profile.preferred_locations if loc_item.strip()]
            if pref_locs_l:
                job_remote = (job.remote_type or "").upper() == "REMOTE"
                can_remote = getattr(profile, "remote_preference", True)
                if job_remote and can_remote:
                    is_loc_excluded = False
                elif job_remote and not can_remote:
                    is_loc_excluded = True
                else:
                    job_loc_l = (job.location or "").lower()
                    job_norm_l = (job.normalized_location or "").lower()
                    loc_matches = any(p in job_loc_l or p in job_norm_l for p in pref_locs_l)
                    ncr_aliases = {"delhi", "noida", "gurgaon", "gurugram", "delhi ncr", "greater noida", "ghaziabad", "faridabad"}
                    if not loc_matches and any(a in pref_locs_l for a in ncr_aliases):
                        if any(a in job_loc_l or a in job_norm_l for a in ncr_aliases):
                            loc_matches = True
                    if not loc_matches:
                        is_loc_excluded = True

        # 5. Unpaid internship check
        from app.utils.normalization import is_unpaid_salary_text
        is_unpaid_role = (
            (job.salary_max == 0.0 and job.salary_min == 0.0)
            or (job.salary_raw and is_unpaid_salary_text(job.salary_raw))
            or (isinstance(job.raw_data, dict) and job.raw_data.get("is_unpaid"))
        )
        is_unpaid_excluded = bool(is_unpaid_role and getattr(preferences, "exclude_unpaid", False))
        # In Recall-First architecture: Do NOT abort or drop job.
        # Informational flags adjust dimension scores rather than gatekeeping.
        exclusion_reasons: list[str] = []
        if is_exp_excluded:
            exp_str = (
                f"{job.experience_min}-{job.experience_max}y"
                if job.experience_min is not None and job.experience_max is not None
                else (f"{job.experience_min}+y" if job.experience_min is not None else "unspecified")
            )
            exclusion_reasons.append(f"Experience required ({exp_str}) exceeds preference ceiling ({pref_max_exp}y)")
        if is_unpaid_excluded:
            exclusion_reasons.append("Unpaid position (preference requires paid positions)")
        if is_loc_excluded:
            exclusion_reasons.append(f"Location '{job.location}' outside preferred locations")
        if is_role_excluded:
            exclusion_reasons.append("Role in candidate's excluded roles")
        if is_comp_excluded:
            exclusion_reasons.append("Company in candidate's excluded companies")

        # 5. Compute Detailed Skill Compatibility
        skill_compat = self.compute_skill_compatibility(
            profile.skills, job.required_skills, job.preferred_skills
        )
        req_score = skill_compat["required_score"]
        pref_skill_score = skill_compat["preferred_score"]
        trans_score = skill_compat["transferable_score"]
        skill_score = skill_compat["skill_score"]
        matched_required = skill_compat["matched_required"]
        missing_required = skill_compat["missing_required"]
        matched_preferred = skill_compat["matched_preferred"]
        missing_preferred = skill_compat["missing_preferred"]
        trans_details = skill_compat["transferable_details"]

        # Backwards compatible lists
        matched_skills = normalize_skills(matched_required + matched_preferred)
        missing_skills = missing_required
        transferable_skills = [
            f"{t['job_skill']} (via {t['candidate_skill']})" for t in trans_details
        ]

        # 6. Semantic Similarity (preserved for ranking/info, weight is 0.0 in primary score)
        job_emb = list(job.embedding) if job.embedding is not None else None
        prof_emb = list(profile.embedding) if profile.embedding is not None else None
        semantic_score = self.compute_semantic_score(job_emb, prof_emb)

        # 7. Experience Score (5% weight)
        exp_score = self.compute_experience_score(
            profile.experience_years or 0,
            job.experience_min,
            job.experience_max,
            job.employment_type,
            profile.internship_allowed,
        )

        # 8. Location Score (5% weight)
        loc_score = self.compute_location_score(
            job.location,
            job.normalized_location,
            job.remote_type,
            profile.preferred_locations,
            profile.remote_preference,
        )

        # 9. Skill-First Weighted Calculation:
        w_req = getattr(settings, "WEIGHT_REQUIRED_SKILL_MATCH", 0.60)
        w_pref_skill = getattr(settings, "WEIGHT_PREFERRED_SKILL_MATCH", 0.15)
        w_trans = getattr(settings, "WEIGHT_TRANSFERABLE_SKILL_MATCH", 0.10)
        w_exp = getattr(settings, "WEIGHT_EXPERIENCE_MATCH", 0.05)
        w_loc = getattr(settings, "WEIGHT_LOCATION_MATCH", 0.05)
        w_pref = getattr(settings, "WEIGHT_PREFERENCE_MATCH", 0.05)

        raw_overall = (
            (req_score * w_req)
            + (pref_skill_score * w_pref_skill)
            + (trans_score * w_trans)
            + (exp_score * w_exp)
            + (loc_score * w_loc)
            + (pref_score * w_pref)
        )

        # 10. Anti-Inflation Gating Guardrails:
        # Semantic similarity and context MUST NOT compensate for missing core skills.
        num_req = len(job.required_skills or [])
        num_matched = len(matched_required)
        num_trans = len([t for t in trans_details if t["job_skill"] in missing_required])

        if num_req == 0:
            # When no required skills could be extracted, job has low confidence and MUST NOT score as STRONG/GOOD match
            raw_overall = min(raw_overall, 45.0)
        elif num_req >= 1:
            transferable_ratio = (trans_score / 100.0) if trans_score else (num_trans / num_req if num_req else 0.0)
            if num_matched == 0:
                if transferable_ratio > 0.40 or (num_trans > 0 and trans_score >= 40.0):
                    # Safe recovery floor to mark as CONSIDER instead of hard SKIP
                    raw_overall = max(raw_overall, 48.0)
                elif num_trans > 0:
                    raw_overall = min(raw_overall, 35.0)
                else:
                    raw_overall = min(raw_overall, 20.0)
            elif (num_matched / num_req) < 0.35:
                # Provide smooth path up to 55% if transferable skills bridge stack gaps
                trans_bonus = (trans_score / 100.0) * 20.0
                raw_overall = min(55.0, max(raw_overall, 35.0 + trans_bonus))

        # 11. Role Eligibility Gating:
        # If job title does not match candidate's target roles, it cannot receive a high score
        # unless candidate possesses >= 80% of the required skills (e.g. backend stack under an unconventional title).
        if is_role_ineligible:
            if num_req == 0 or req_score < 80.0 or num_matched < 2:
                raw_overall = min(raw_overall, 30.0)

        overall = round(max(0.0, min(100.0, raw_overall)), 1)

        # Recommendation classification
        if overall >= 80.0:
            recommendation = "STRONG_MATCH"
        elif overall >= 65.0:
            recommendation = "GOOD_MATCH"
        elif overall >= 50.0:
            recommendation = "CONSIDER"
        elif overall >= 35.0:
            recommendation = "LOW_PRIORITY"
        else:
            recommendation = "SKIP"

        # 12. Confidence Calculation
        confidence, confidence_label = self.compute_confidence(
            job, job.required_skills, job.preferred_skills
        )

        # Deterministic explainability
        req_summary = f"{num_matched}/{num_req} required skills" if num_req else "no specific required skills listed"
        matched_str = ", ".join(matched_required) if matched_required else "none"
        missing_str = ", ".join(missing_required) if missing_required else "none"
        trans_str = f" Transferable: {', '.join(transferable_skills)}." if transferable_skills else ""

        explanation = (
            f"Overall: {overall}% ({recommendation.replace('_', ' ')}). "
            f"Skill match: {skill_score}%. Matched {req_summary} ({matched_str}). "
            f"Missing required: {missing_str}.{trans_str}"
        )

        return {
            "overall_score": overall,
            "skill_score": skill_score,
            "semantic_score": semantic_score,
            "experience_score": exp_score,
            "role_score": role_score,
            "location_score": loc_score,
            "preference_score": pref_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "transferable_skills": transferable_skills,
            "required_skills": {
                "matched": matched_required,
                "missing": missing_required,
            },
            "preferred_skills": {
                "matched": matched_preferred,
                "missing": missing_preferred,
            },
            "transferable_details": trans_details,
            "experience_eligible": not is_exp_excluded,
            "location_eligible": not is_loc_excluded,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "experience_match": {
                "score": exp_score,
                "eligible": not is_exp_excluded,
            },
            "location_match": {
                "score": loc_score,
                "eligible": not is_loc_excluded,
            },
            "preference_match": {
                "score": pref_score,
                "eligible": not is_comp_excluded and not is_unpaid_excluded,
            },
            "explanation": explanation,
            "recommendation": recommendation,
            "is_excluded": bool(exclusion_reasons),
            "exclusion_reasons": exclusion_reasons,
        }

    ALGORITHM_VERSION = "v2.1"

    @staticmethod
    def compute_profile_version(profile: CandidateProfile | None) -> str:
        if not profile:
            return "none"
        import hashlib, json
        data = {
            "skills": sorted([s.lower().strip() for s in (profile.skills or [])]),
            "target_roles": sorted([r.lower().strip() for r in (profile.target_roles or [])]),
            "excluded_roles": sorted([r.lower().strip() for r in (profile.excluded_roles or [])]),
            "experience_years": profile.experience_years or 0,
            "experience_level": profile.experience_level or "FRESHER",
            "preferred_locations": sorted([l.lower().strip() for l in (profile.preferred_locations or [])]),
            "remote_preference": bool(profile.remote_preference),
            "minimum_salary_lpa": profile.minimum_salary_lpa or 0.0,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    @staticmethod
    def compute_job_version(job: Job) -> str:
        import hashlib, json
        data = {
            "title": (job.title or "").strip().lower(),
            "role_category": (job.role_category or "").strip().lower(),
            "company_name": (job.company_name or "").strip().lower(),
            "location": (job.location or "").strip().lower(),
            "remote_type": (job.remote_type or "").strip().lower(),
            "employment_type": (job.employment_type or "").strip().lower(),
            "experience_min": job.experience_min,
            "experience_max": job.experience_max,
            "required_skills": sorted([s.lower().strip() for s in (job.required_skills or [])]),
            "preferred_skills": sorted([s.lower().strip() for s in (job.preferred_skills or [])]),
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    @staticmethod
    def compute_preference_version(preferences: Preference | None) -> str:
        if not preferences:
            return "default"
        import hashlib, json
        data = {
            "priority_companies": sorted([c.lower().strip() for c in (preferences.priority_companies or [])]),
            "excluded_companies": sorted([c.lower().strip() for c in (preferences.excluded_companies or [])]),
            "experience_max_years": preferences.experience_max_years,
            "freshness_hours": preferences.freshness_hours,
            "preferred_technologies": sorted([t.lower().strip() for t in (preferences.preferred_technologies or [])]),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    async def get_or_calculate_match(
        self, db: AsyncSession, job: Job, profile: CandidateProfile, preferences: Preference | None = None
    ) -> Match:
        """Fetches existing match if versions match, or calculates and persists it."""
        p_ver = self.compute_profile_version(profile)
        j_ver = self.compute_job_version(job)
        pref_ver = self.compute_preference_version(preferences)
        algo_ver = self.ALGORITHM_VERSION

        stmt = select(Match).where(Match.job_id == job.id, Match.profile_id == profile.id)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        # Cache Hit Check
        if (
            existing
            and existing.algorithm_version == algo_ver
            and existing.profile_version == p_ver
            and existing.job_version == j_ver
            and existing.preference_version == pref_ver
        ):
            return existing

        eval_data = self.evaluate_job(job, profile, preferences)

        if existing:
            existing.overall_score = eval_data["overall_score"]
            existing.skill_score = eval_data["skill_score"]
            existing.semantic_score = eval_data["semantic_score"]
            existing.experience_score = eval_data["experience_score"]
            existing.role_score = eval_data["role_score"]
            existing.location_score = eval_data["location_score"]
            existing.preference_score = eval_data["preference_score"]
            existing.matched_skills = eval_data["matched_skills"]
            existing.missing_skills = eval_data["missing_skills"]
            existing.transferable_skills = eval_data["transferable_skills"]
            existing.confidence = eval_data["confidence"]
            existing.confidence_label = eval_data["confidence_label"]
            existing.explanation = eval_data["explanation"]
            existing.recommendation = eval_data["recommendation"]
            existing.algorithm_version = algo_ver
            existing.profile_version = p_ver
            existing.job_version = j_ver
            existing.preference_version = pref_ver
            existing.calculated_at = datetime.now(timezone.utc)
            match_record = existing
        else:
            match_record = Match(
                id=uuid.uuid4(),
                job_id=job.id,
                profile_id=profile.id,
                overall_score=eval_data["overall_score"],
                skill_score=eval_data["skill_score"],
                semantic_score=eval_data["semantic_score"],
                experience_score=eval_data["experience_score"],
                role_score=eval_data["role_score"],
                location_score=eval_data["location_score"],
                preference_score=eval_data["preference_score"],
                matched_skills=eval_data["matched_skills"],
                missing_skills=eval_data["missing_skills"],
                transferable_skills=eval_data["transferable_skills"],
                confidence=eval_data["confidence"],
                confidence_label=eval_data["confidence_label"],
                explanation=eval_data["explanation"],
                recommendation=eval_data["recommendation"],
                algorithm_version=algo_ver,
                profile_version=p_ver,
                job_version=j_ver,
                preference_version=pref_ver,
                calculated_at=datetime.now(timezone.utc),
            )
            db.add(match_record)

        await db.commit()
        await db.refresh(match_record)
        return match_record

    async def bulk_get_or_calculate_matches(
        self,
        db: AsyncSession,
        jobs: list[Job],
        profile: CandidateProfile,
        preferences: Preference | None = None,
        strict_location: bool = False,
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """
        Bulk retrieves cached matches or calculates missing/invalid ones.
        Single DB query for existing matches, eliminating per-job DB reads.
        """
        if not jobs or not profile:
            return {}

        p_ver = self.compute_profile_version(profile)
        pref_ver = self.compute_preference_version(preferences)
        algo_ver = self.ALGORITHM_VERSION

        job_map = {j.id: j for j in jobs}
        job_ids = list(job_map.keys())

        stmt = select(Match).where(
            Match.profile_id == profile.id,
            Match.job_id.in_(job_ids)
        )
        res = await db.execute(stmt)
        existing_matches = {m.job_id: m for m in res.scalars().all()}

        results: dict[uuid.UUID, dict[str, Any]] = {}
        to_persist: list[Match] = []

        for job_id, job in job_map.items():
            j_ver = self.compute_job_version(job)
            existing = existing_matches.get(job_id)

            if (
                existing
                and existing.algorithm_version == algo_ver
                and existing.profile_version == p_ver
                and existing.job_version == j_ver
                and existing.preference_version == pref_ver
            ):
                # Cache hit: reconstruct eval_data dict
                eval_res = {
                    "overall_score": existing.overall_score,
                    "skill_score": existing.skill_score,
                    "semantic_score": existing.semantic_score,
                    "experience_score": existing.experience_score,
                    "role_score": existing.role_score,
                    "location_score": existing.location_score,
                    "preference_score": existing.preference_score,
                    "matched_skills": existing.matched_skills,
                    "missing_skills": existing.missing_skills,
                    "transferable_skills": existing.transferable_skills,
                    "required_skills": job.required_skills or [],
                    "preferred_skills": job.preferred_skills or [],
                    "transferable_details": [],
                    "experience_eligible": True,
                    "location_eligible": True,
                    "confidence": existing.confidence,
                    "confidence_label": existing.confidence_label,
                    "explanation": existing.explanation,
                    "recommendation": existing.recommendation,
                }
                results[job_id] = eval_res
            else:
                # Cache miss / version mismatch: calculate deterministically
                eval_res = self.evaluate_job(
                    job, profile, preferences, strict_location=strict_location
                )
                results[job_id] = eval_res

                if existing:
                    existing.overall_score = eval_res["overall_score"]
                    existing.skill_score = eval_res["skill_score"]
                    existing.semantic_score = eval_res["semantic_score"]
                    existing.experience_score = eval_res["experience_score"]
                    existing.role_score = eval_res["role_score"]
                    existing.location_score = eval_res["location_score"]
                    existing.preference_score = eval_res["preference_score"]
                    existing.matched_skills = eval_res["matched_skills"]
                    existing.missing_skills = eval_res["missing_skills"]
                    existing.transferable_skills = eval_res["transferable_skills"]
                    existing.confidence = eval_res.get("confidence", 1.0)
                    existing.confidence_label = eval_res.get("confidence_label", "HIGH")
                    existing.explanation = eval_res["explanation"]
                    existing.recommendation = eval_res["recommendation"]
                    existing.algorithm_version = algo_ver
                    existing.profile_version = p_ver
                    existing.job_version = j_ver
                    existing.preference_version = pref_ver
                    existing.calculated_at = datetime.now(timezone.utc)
                else:
                    new_m = Match(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        profile_id=profile.id,
                        overall_score=eval_res["overall_score"],
                        skill_score=eval_res["skill_score"],
                        semantic_score=eval_res["semantic_score"],
                        experience_score=eval_res["experience_score"],
                        role_score=eval_res["role_score"],
                        location_score=eval_res["location_score"],
                        preference_score=eval_res["preference_score"],
                        matched_skills=eval_res["matched_skills"],
                        missing_skills=eval_res["missing_skills"],
                        transferable_skills=eval_res["transferable_skills"],
                        confidence=eval_res.get("confidence", 1.0),
                        confidence_label=eval_res.get("confidence_label", "HIGH"),
                        explanation=eval_res["explanation"],
                        recommendation=eval_res["recommendation"],
                        algorithm_version=algo_ver,
                        profile_version=p_ver,
                        job_version=j_ver,
                        preference_version=pref_ver,
                        calculated_at=datetime.now(timezone.utc),
                    )
                    db.add(new_m)
                to_persist.append(existing or new_m)

        if to_persist:
            try:
                await db.commit()
            except Exception as e:
                logger.warning("bulk_match_persist_error", error=str(e))
                await db.rollback()

        return results


_default_matching_service: MatchingService | None = None


def get_matching_service() -> MatchingService:
    global _default_matching_service
    if _default_matching_service is None:
        _default_matching_service = MatchingService()
    return _default_matching_service
