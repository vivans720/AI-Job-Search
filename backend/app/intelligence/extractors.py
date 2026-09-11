import io
from typing import Any
import pdfplumber
import docx
import structlog

from app.intelligence.llm_provider import LLMProvider, get_llm_provider
from app.utils.normalization import normalize_skills

logger = structlog.get_logger(__name__)

RESUME_EXTRACTION_SYSTEM_PROMPT = """You are an expert technical candidate profiler and resume analyst.
Analyze the provided resume text and extract a comprehensive, structured candidate profile in JSON.

Guidelines:
1. Do NOT hallucinate or invent information not present in the resume.
2. For fresh graduates / current students with only internships or academic projects, classify experience_level as "FRESHER" and experience_years as 0.
3. Determine target_roles strictly supported by the candidate's demonstrable skills and projects. Prioritize roles like:
   - Full Stack Developer / Engineer
   - Backend Developer / Engineer
   - Frontend Developer / Engineer
   - Software Engineer / Developer
   - AI / ML Engineer
   - Generative AI Engineer
4. Categorize technologies cleanly into programming_languages, frameworks, databases, cloud, and tools.
5. Return ONLY a valid JSON object matching the requested schema.
"""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF file using pdfplumber."""
    pages_text = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract plain text from a DOCX file."""
    doc = docx.Document(io.BytesIO(file_bytes))
    full_text = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(full_text).strip()


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF, DOCX, or plain text based on file extension."""
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif lower_name.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif lower_name.endswith((".txt", ".md")):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        # Attempt PDF first, then UTF-8 decode
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            return file_bytes.decode("utf-8", errors="replace")


async def extract_candidate_profile_from_text(
    resume_text: str, llm: LLMProvider | None = None
) -> dict[str, Any]:
    """Uses the LLM provider to extract structured candidate intelligence from raw resume text."""
    if not llm:
        llm = get_llm_provider()

    prompt = f"""Extract the structured candidate profile from this resume:

--- RESUME TEXT ---
{resume_text}
--- END OF RESUME ---

Return JSON with exactly these keys:
{{
  "candidate_name": "Full Name",
  "email": "email@example.com or null",
  "experience_level": "FRESHER" or "0-1" or "1-2" or "ENTRY_LEVEL",
  "experience_years": 0,
  "target_roles": ["Full Stack Developer", "Backend Developer", "AI Engineer"],
  "programming_languages": ["Python", "JavaScript"],
  "frameworks": ["FastAPI", "React", "Node.js"],
  "databases": ["PostgreSQL", "MongoDB"],
  "cloud": ["AWS", "Docker"],
  "tools": ["Git", "Postman"],
  "skills": ["REST APIs", "Vector Search", "System Design"],
  "education": [
    {{
      "degree": "B.Tech in Computer Science",
      "institution": "University Name",
      "graduation_year": 2026,
      "grade": "8.5 CGPA or null"
    }}
  ],
  "projects": [
    {{
      "title": "Project Name",
      "description": "Brief description of what was built and impact",
      "technologies": ["Python", "FastAPI"],
      "link": "https://github.com/... or null"
    }}
  ],
  "work_experience": [
    {{
      "title": "Intern / Developer",
      "company": "Company Name",
      "duration": "June 2024 - August 2024",
      "description": "Responsibilities and achievements",
      "type": "INTERNSHIP" or "FULL_TIME"
    }}
  ],
  "certifications": ["Certification Name"],
  "preferred_locations": ["Bengaluru", "Remote"],
  "summary": "Concise 2-sentence technical summary"
}}
"""

    messages = [
        {"role": "system", "content": RESUME_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    raw_profile = await llm.complete_json(messages)

    # Normalize extracted skill collections
    raw_profile["programming_languages"] = normalize_skills(
        raw_profile.get("programming_languages", [])
    )
    raw_profile["frameworks"] = normalize_skills(raw_profile.get("frameworks", []))
    raw_profile["databases"] = normalize_skills(raw_profile.get("databases", []))
    raw_profile["cloud"] = normalize_skills(raw_profile.get("cloud", []))
    raw_profile["tools"] = normalize_skills(raw_profile.get("tools", []))

    all_combined = (
        raw_profile["programming_languages"]
        + raw_profile["frameworks"]
        + raw_profile["databases"]
        + raw_profile["cloud"]
        + raw_profile["tools"]
        + normalize_skills(raw_profile.get("skills", []))
    )
    raw_profile["skills"] = normalize_skills(all_combined)

    return raw_profile
