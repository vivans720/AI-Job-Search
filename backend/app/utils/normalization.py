import re
from typing import Any

CANONICAL_SKILLS: dict[str, str] = {
    # Languages
    "python": "Python",
    "python3": "Python",
    "python 3": "Python",
    "py": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ecmascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "html5": "HTML5",
    "css3": "CSS3",
    # Frameworks & Libraries
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "react native": "React Native",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "fastapi": "FastAPI",
    "fast api": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "vite": "Vite",
    "pydantic": "Pydantic",
    "socket.io": "Socket.IO",
    "webrtc": "WebRTC",
    # Databases & Caching
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgresql db": "PostgreSQL",
    "psql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "pgvector": "pgvector",
    # Data Engineering & Analytics
    "etl": "ETL",
    "dbt": "dbt",
    "snowflake": "Snowflake",
    "airflow": "Airflow",
    "apache airflow": "Airflow",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "looker": "Looker Studio",
    "looker studio": "Looker Studio",
    "tableau": "Tableau",
    "data warehousing": "Data Warehousing",
    "data warehouse": "Data Warehousing",
    "data pipelines": "Data Pipelines",
    "data pipeline": "Data Pipelines",
    "kafka": "Kafka",
    "apache kafka": "Kafka",
    "spark": "Apache Spark",
    "apache spark": "Apache Spark",
    "pyspark": "PySpark",
    "bigquery": "BigQuery",
    # Cloud, DevOps & APIs
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "azure": "Azure",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "git": "Git",
    "github": "GitHub",
    "ci/cd": "CI/CD",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "restful apis": "REST APIs",
    "restful api": "REST APIs",
    "rest": "REST APIs",
    "restful": "REST APIs",
    "graphql": "GraphQL",
    # AI / ML
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "ai": "Artificial Intelligence",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "llm": "LLM",
    "llms": "LLM",
    "rag": "RAG",
    "nlp": "NLP",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "prompt engineering": "Prompt Engineering",
    "vector search": "Vector Search",
}

CANONICAL_LOCATIONS: dict[str, str] = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bangaluru": "Bengaluru",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "delhi": "Delhi NCR",
    "delhi ncr": "Delhi NCR",
    "new delhi": "Delhi NCR",
    "noida": "Delhi NCR",
    "greater noida": "Delhi NCR",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "chennai": "Chennai",
    "madras": "Chennai",
    "kolkata": "Kolkata",
    "calcutta": "Kolkata",
    "remote": "Remote",
    "india": "India",
    "remote - india": "Remote (India)",
    "work from home": "Remote",
}


def normalize_skill(skill: str) -> str:
    """Normalize a raw skill string to canonical form."""
    cleaned = skill.strip()
    key = cleaned.lower()
    return CANONICAL_SKILLS.get(key, cleaned)


def normalize_skills(skills: list[str]) -> list[str]:
    """Normalize a list of skills and deduplicate preserving order."""
    seen = set()
    result = []
    for s in skills:
        norm = normalize_skill(s)
        if norm.lower() not in seen and norm.strip():
            seen.add(norm.lower())
            result.append(norm)
    return result


def scan_skills_in_text(text: str) -> list[str]:
    """
    Scans text for canonical skills using strict word boundaries.
    Prevents false-positives like 'rag' matching inside 'encouraged' or 'storage'.
    Matches multi-word skills first to prevent premature sub-token matching.
    """
    if not text or not text.strip():
        return []

    found: list[tuple[int, int, str]] = []  # (start, end, canonical_name)

    # Sort keys by length descending so longer phrases match before sub-phrases
    for key, canonical in sorted(CANONICAL_SKILLS.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(r"[^a-zA-Z0-9\s]", key):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])"
        else:
            pattern = rf"\b{re.escape(key)}\b"

        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            s, e = match.start(), match.end()
            # Check overlap with existing larger matches
            overlap = any(
                (s >= exist_s and s < exist_e) or (e > exist_s and e <= exist_e)
                for exist_s, exist_e, _ in found
            )
            if not overlap:
                found.append((s, e, canonical))

    # Sort by start position
    found.sort(key=lambda x: x[0])
    return normalize_skills([name for _, _, name in found])


def extract_skills_from_text(
    description: str,
    title: str | None = None,
    explicit_skills: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Extracts required and preferred skills separately from job description and tags.
    Uses section headers to partition into Required vs Preferred/Nice-to-have.
    Uses strict regex word boundaries to prevent substring false-positives.
    Returns: (required_skills, preferred_skills)
    """
    # Scan description for sections
    full_text = description or ""

    # Check for preferred / nice to have section
    pref_header_pattern = re.compile(
        r"(?:^|\n)\s*(?:(?:good|nice)\s+to\s+have|preferred(?:\s+qualifications|\s+skills)?|bonus\s+points?|plus\s+points?|desired\s+skills|optional\s+skills)[:\s\-]",
        re.IGNORECASE,
    )
    req_header_pattern = re.compile(
        r"(?:^|\n)\s*(?:requirements?|required\s+skills?|must\s+have|what\s+you(?:'ll|\s+will)?\s+need|key\s+skills?|technical\s+skills?|qualifications?|mandatory\s+skills?|responsibilities)[:\s\-]",
        re.IGNORECASE,
    )

    pref_match = pref_header_pattern.search(full_text)

    required_skills: list[str] = []
    preferred_skills: list[str] = []

    if explicit_skills:
        required_skills.extend(normalize_skills(explicit_skills))

    # Scan title for specific concrete technologies (e.g. Python in 'Python Backend Intern'),
    # but filter out generic role title words (AI, ML, Deep Learning) to prevent false positives
    if title:
        role_title_words = {
            "ai",
            "artificial intelligence",
            "ml",
            "machine learning",
            "dl",
            "deep learning",
            "genai",
            "generative ai",
        }
        title_skills = [
            s for s in scan_skills_in_text(title)
            if s.lower() not in role_title_words
        ]
        required_skills.extend(title_skills)

    if pref_match:
        pref_start = pref_match.start()
        after_pref = full_text[pref_match.end():]
        next_section = req_header_pattern.search(after_pref)
        if next_section:
            pref_end = pref_match.end() + next_section.start()
            pref_text = full_text[pref_start:pref_end]
            req_text = full_text[:pref_start] + "\n" + full_text[pref_end:]
        else:
            pref_text = full_text[pref_start:]
            req_text = full_text[:pref_start]

        preferred_skills.extend(scan_skills_in_text(pref_text))
        required_skills.extend(scan_skills_in_text(req_text))
    else:
        # No distinct preferred section: all scanned skills are required
        required_skills.extend(scan_skills_in_text(full_text))

    # Deduplicate: if a skill is in required, it should not be in preferred
    req_norm = normalize_skills(required_skills)
    req_set = {s.lower() for s in req_norm}
    pref_norm = [s for s in normalize_skills(preferred_skills) if s.lower() not in req_set]

    return req_norm, pref_norm


def normalize_location(location: str | None) -> str:
    """Normalize Indian location names to standard forms (e.g. Bengaluru)."""
    if not location:
        return "Unknown"
    cleaned = location.strip()
    if not cleaned:
        return "Unknown"

    # Multi-location separator support (e.g. "Bengaluru / Hyderabad", "Pune, Mumbai")
    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        resolved_parts = [normalize_location(p) for p in parts]
        # Deduplicate preserving order
        seen = set()
        deduped = []
        for r in resolved_parts:
            if r not in seen and r != "Unknown":
                seen.add(r)
                deduped.append(r)
        return " / ".join(deduped) if deduped else "Unknown"

    from app.core.location_taxonomy import resolve_canonical_location
    resolved = resolve_canonical_location(cleaned)
    return resolved.canonical_name


def is_unpaid_salary_text(text: str | None) -> bool:
    """Detects if raw salary string represents an unpaid or volunteer position."""
    if not text:
        return False
    t = text.strip().lower()
    return bool(re.search(r"\b(unpaid|no\s+stipend|expenses\s+only|volunteer|zero\s+stipend|performance\s+based|incentives?\s+only)\b", t))


def parse_salary_text(raw: str | None) -> dict[str, Any]:
    """Parses raw salary string into structured min/max values in INR."""
    if not raw:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": None,
            "is_unpaid": False,
        }

    text = raw.strip().lower().replace(",", "")

    # Check explicit unpaid/volunteer indicators
    if is_unpaid_salary_text(text):
        return {
            "salary_min": 0.0,
            "salary_max": 0.0,
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": raw,
            "is_unpaid": True,
        }

    cr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(?:cr|crore)", text)
    if cr_match:
        val1 = float(cr_match.group(1)) * 10000000
        val2 = float(cr_match.group(2)) * 10000000 if cr_match.group(2) else val1
        return {
            "salary_min": min(val1, val2),
            "salary_max": max(val1, val2),
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": raw,
        }

    lpa_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lakh|lac)", text)
    if lpa_match:
        val1 = float(lpa_match.group(1)) * 100000
        val2 = float(lpa_match.group(2)) * 100000 if lpa_match.group(2) else val1
        return {
            "salary_min": min(val1, val2),
            "salary_max": max(val1, val2),
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": raw,
        }

    monthly_match = re.search(r"(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:/month|per month|pm)", text)
    if monthly_match:
        val1 = float(monthly_match.group(1)) * 12
        val2 = float(monthly_match.group(2)) * 12 if monthly_match.group(2) else val1
        return {
            "salary_min": min(val1, val2),
            "salary_max": max(val1, val2),
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": raw,
        }

    annual_inr_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{5,8})\s*(?:-|to)?\s*(\d{5,8})?", text)
    if annual_inr_match:
        val1 = float(annual_inr_match.group(1))
        val2 = float(annual_inr_match.group(2)) if annual_inr_match.group(2) else val1
        return {
            "salary_min": min(val1, val2),
            "salary_max": max(val1, val2),
            "salary_currency": "INR",
            "salary_period": "YEAR",
            "salary_raw": raw,
        }

    return {
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
        "salary_period": "YEAR",
        "salary_raw": raw,
    }


def categorize_role(title: str) -> str:
    """Categorizes a job title into standard role taxonomy."""
    lower = title.lower()

    if any(k in lower for k in ["full stack", "fullstack", "full-stack"]):
        return "FULL_STACK"
    if any(k in lower for k in ["genai", "generative ai", "llm"]):
        return "GEN_AI"
    if any(k in lower for k in ["machine learning", "ml engineer", "nlp", "computer vision"]):
        return "ML_ENGINEERING"
    if any(k in lower for k in ["ai engineer", "artificial intelligence"]):
        return "AI_ENGINEERING"
    if any(k in lower for k in ["frontend", "front-end", "front end", "react", "ui developer"]):
        return "FRONTEND"
    if any(k in lower for k in ["backend", "back-end", "back end", "python dev", "node dev", "api engineer"]):
        return "BACKEND"
    if any(k in lower for k in ["devops", "cloud engineer", "sre", "platform engineer"]):
        return "DEVOPS"
    if any(k in lower for k in ["data engineer", "data analyst", "data scientist"]):
        return "DATA"
    return "SOFTWARE_ENGINEERING"


def normalize_title(title: str) -> tuple[str, str]:
    """
    Standardizes a raw job title and assigns its taxonomy category.
    Returns (normalized_title, role_category).
    """
    category = categorize_role(title)
    cleaned = re.sub(r"\s+", " ", title).strip()

    # Common abbreviation replacements
    replacements = [
        (r"\bSDE[\s-]*1\b", "Software Development Engineer I"),
        (r"\bSDE[\s-]*I\b", "Software Development Engineer I"),
        (r"\bSDE[\s-]*2\b", "Software Development Engineer II"),
        (r"\bSDE\b", "Software Development Engineer"),
        (r"\bSWE\b", "Software Engineer"),
        (r"\bDev\b", "Developer"),
        (r"\bEngg\b", "Engineer"),
        (r"\bJr\.?\b", "Junior"),
        (r"\bSr\.?\b", "Senior"),
    ]
    norm = cleaned
    for pat, rep in replacements:
        norm = re.sub(pat, rep, norm, flags=re.IGNORECASE)

    return norm, category


ROLE_CLUSTERS: dict[str, set[str]] = {
    "software_engineer": {
        "software engineer", "software developer", "software development engineer",
        "sde", "sde-1", "sde 1", "sde-i", "swe", "software engineering", "software dev",
        "junior developer", "graduate engineer", "associate software engineer",
        "graduate software engineer"
    },
    "full_stack": {
        "full stack", "fullstack", "full-stack", "mern", "mean", "web developer",
        "full stack developer", "full stack engineer", "fullstack developer",
        "fullstack engineer", "full stack web developer", "web development"
    },
    "ai_ml": {
        "ai", "ml", "ai/ml", "ai-ml", "machine learning", "artificial intelligence",
        "deep learning", "genai", "generative ai", "llm", "ai engineer", "ml engineer",
        "machine learning engineer", "ai/ml engineer", "ai developer", "nlp engineer",
        "data science", "data scientist"
    },
    "backend": {
        "backend", "back end", "back-end", "backend developer", "backend engineer",
        "api developer", "server engineer", "python developer", "python engineer",
        "node developer", "django developer", "fastapi developer"
    },
    "frontend": {
        "frontend", "front end", "front-end", "frontend developer", "frontend engineer",
        "ui developer", "react developer", "web developer", "ui/ux developer"
    },
    "python": {
        "python", "python developer", "python engineer"
    },
}


def matches_target_role(
    job_title: str,
    target_roles: list[str],
    role_category: str | None = None,
) -> bool:
    """
    Robust role and alias matching between a job title and candidate target roles.
    Handles hyphens, slashes, compound words (Fullstack vs Full Stack),
    abbreviations (SDE-1), qualifiers ('Software Engineer - Early Career'),
    and role synonyms (Developer vs Engineer).
    """
    if not target_roles:
        return True

    title_raw = (job_title or "").strip().lower()
    if not title_raw:
        return False

    title_norm = re.sub(r"[/_\-]", " ", title_raw)
    norm_t, cat = normalize_title(title_raw)
    norm_t_low = norm_t.lower()

    active_aliases: set[str] = set()
    direct_targets: set[str] = set()

    for r in target_roles:
        r_clean = r.strip().lower()
        if not r_clean:
            continue
        r_base = re.sub(
            r"\s*-\s*(?:early career|junior|entry level|fresher|trainee|senior|lead).*",
            "",
            r_clean,
        ).strip()
        direct_targets.add(r_clean)
        if r_base:
            direct_targets.add(r_base)

        for cluster_name, aliases in ROLE_CLUSTERS.items():
            if any(alias in r_clean or (r_base and alias in r_base) for alias in aliases):
                active_aliases.update(aliases)

    # 1. Direct check against targets
    for target in direct_targets:
        if target in title_raw or target in title_norm or target in norm_t_low:
            return True

    # 2. Check active aliases
    for alias in active_aliases:
        if " " in alias or len(alias) > 3:
            if alias in title_raw or alias in title_norm or alias in norm_t_low:
                return True
        else:
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, title_raw) or re.search(pattern, title_norm):
                return True

    return False


def parse_experience_requirement(
    text: str | None,
) -> tuple[int | None, int | None, str | None, str]:
    """
    Parses experience requirements into (min_years, max_years, experience_text, confidence).
    Preserves uncertainty: if unparseable, returns (None, None, text, 'LOW').
    Fixes '5 days a week' bug: strictly requires year tokens and rejects day/week tokens.
    """
    if not text or not text.strip():
        return None, None, None, "LOW"

    cleaned = text.strip()
    t = cleaned.lower()

    # Explicit rejection of day/week/shift patterns (e.g. '5 days a week', '6 days/week', 'working 5 days')
    if re.search(r"\b\d+\s*(?:days?|weeks?|hours?|hrs?|months?)\s*(?:a|per|\/)\s*(?:week|month|day)\b", t):
        if not re.search(r"\b(?:years?|yrs?|yr|fresher|intern|experience|exp)\b", t):
            snippet = cleaned if len(cleaned) <= 100 else cleaned[:100].strip()
            return None, None, snippet, "LOW"

    # 1. Fresher / Entry Level / Internship
    m_fresh = re.search(r"\b(fresher|freshers|entry\s+level|no\s+experience|0\s*(?:-|to)\s*0\s*(?:yrs?|years?)|intern|internship|graduate)\b", t)
    if m_fresh:
        m_range = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?|yr)\b", t)
        if not m_range:
            snippet = cleaned if len(cleaned) <= 100 else m_fresh.group(0)
            return 0, 0, snippet, "HIGH"

    # 2. Explicit range with REQUIRED year units (e.g. '0-2 years', '1 to 3 yrs')
    m_range = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?|yr)\b", t)
    if m_range:
        snippet = cleaned if len(cleaned) <= 100 else m_range.group(0)
        return int(m_range.group(1)), int(m_range.group(2)), snippet, "HIGH"

    # 3. Explicit plus with REQUIRED year units (e.g. '2+ years', '3+ yrs')
    m_plus = re.search(r"(\d+)\s*\+\s*(?:years?|yrs?|yr)\b", t)
    if m_plus:
        v = int(m_plus.group(1))
        snippet = cleaned if len(cleaned) <= 100 else m_plus.group(0)
        return v, None, snippet, "HIGH"

    # 4. Explicit single year requirement (e.g. '1 year', '2 yrs', 'at least 3 years')
    m_single = re.search(r"(?:at\s+least|min(?:imum)?\s*)?(\d+)\s*(?:years?|yrs?|yr)\b", t)
    if m_single:
        v = int(m_single.group(1))
        snippet = cleaned if len(cleaned) <= 100 else m_single.group(0)
        if re.search(r"\b(?:at\s+least|min(?:imum)?|minimum\s+of)\s*" + str(v), t):
            return v, None, snippet, "HIGH"
        return v, v, snippet, "HIGH"

    # 5. Contextual experience prefix with explicit keyword (e.g. 'experience: 1-2', 'exp: 0 to 1')
    m_ctx_range = re.search(r"(?:experience|exp)[:\s]+(\d+)\s*(?:-|to)\s*(\d+)\b(?!\s*(?:days?|weeks?|hours?|months?))", t)
    if m_ctx_range:
        snippet = cleaned if len(cleaned) <= 100 else m_ctx_range.group(0)
        return int(m_ctx_range.group(1)), int(m_ctx_range.group(2)), snippet, "HIGH"

    m_ctx_single = re.search(r"(?:experience|exp)[:\s]+(\d+)\b(?!\s*(?:days?|weeks?|hours?|months?))", t)
    if m_ctx_single:
        v = int(m_ctx_single.group(1))
        snippet = cleaned if len(cleaned) <= 100 else m_ctx_single.group(0)
        return v, v, snippet, "HIGH"

    # 6. Preserved uncertainty only if text explicitly mentions experience/tenure tokens
    if re.search(r"\b(?:years?|yrs?|yr|experience|exp|fresher|intern|entry\s*level)\b", t):
        snippet = cleaned if len(cleaned) <= 100 else None
        return None, None, snippet, "LOW"

    return None, None, None, "LOW"


def infer_experience_from_title(title: str | None) -> tuple[int | None, int | None, str | None, str]:
    """
    Infers approximate experience requirement and seniority bracket from job title.
    Returns: (exp_min, exp_max, exp_text, confidence)
    """
    if not title or not title.strip():
        return None, None, None, "LOW"

    # Normalize separators like underscores, dashes, slashes to spaces
    t = re.sub(r"[_\-\/\\]+", " ", title.strip().lower())

    # 1. Executive / Leadership
    if re.search(r"\b(?:director|vp|vice\s+president|head\s+of|chief|cxo|cto|cfo|cmo|coo)\b", t):
        return 8, None, "Leadership / Director (8+ yrs)", "MEDIUM"

    # 2. Staff / Principal / Architect / Lead
    if re.search(r"\b(?:principal|architect|staff\s+(?:engineer|developer)|tech\s+lead|team\s+lead|lead\s+(?:engineer|developer|architect))\b", t):
        return 7, None, "Lead / Principal (7+ yrs)", "MEDIUM"

    # 3. Senior / SDE 3 / Specialist
    if re.search(r"\b(?:senior|sr\.?|sde\s*(?:3|iii)|developer\s*(?:3|iii)|engineer\s*(?:3|iii)|specialist)\b", t):
        return 5, None, "Senior (5+ yrs)", "MEDIUM"

    # 4. Mid-level / SDE 2
    if re.search(r"\b(?:mid|mid-level|sde\s*(?:2|ii)|developer\s*(?:2|ii)|engineer\s*(?:2|ii))\b", t):
        return 2, 5, "Mid-Level (2-5 yrs)", "MEDIUM"

    # 5. Junior / Associate / SDE 1 / Entry-level
    if re.search(r"\b(?:junior|jr\.?|associate|sde\s*(?:1|i)\b|developer\s*(?:1|i)\b|engineer\s*(?:1|i)\b|entry\s*level|graduate)\b", t):
        return 1, 3, "Junior / Associate (1-3 yrs)", "MEDIUM"

    # 6. Intern / Trainee / Fresher
    if re.search(r"\b(?:intern|internship|trainee|apprentice|fresher)\b", t):
        return 0, 1, "Fresher / Intern (0-1 yrs)", "HIGH"

    return None, None, None, "LOW"


