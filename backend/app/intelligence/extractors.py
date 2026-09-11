import io
import uuid
from typing import Any
import pdfplumber
import docx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.llm_provider import LLMProvider, get_llm_provider
from app.intelligence.service import AIService
from app.intelligence.schemas import CandidateProfileOutput, JobEnrichmentOutput
from app.models.job import Job

logger = structlog.get_logger(__name__)


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
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            return file_bytes.decode("utf-8", errors="replace")


async def extract_candidate_profile_from_text(
    resume_text: str, llm: LLMProvider | None = None
) -> dict[str, Any]:
    """Phase 40: Structured candidate intelligence extraction via AIService returning dictionary representation."""
    service = AIService(provider=llm)
    profile: CandidateProfileOutput = await service.extract_candidate_profile(resume_text)
    return profile.model_dump()


async def enrich_job_record_llm(
    job_id: uuid.UUID,
    db: AsyncSession,
    service: AIService | None = None,
) -> JobEnrichmentOutput | None:
    """Phase 40: Enriches an existing stored job record with LLM intelligence and updates DB."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None

    ai_svc = service or AIService()
    enrichment = await ai_svc.enrich_job(job.title, job.description, job.raw_data)

    # Persist enrichment back onto Job model
    if enrichment.required_skills:
        job.required_skills = enrichment.required_skills
    if enrichment.preferred_skills:
        job.preferred_skills = enrichment.preferred_skills
    if enrichment.standardized_title and not job.normalized_title:
        job.normalized_title = enrichment.standardized_title
    if enrichment.role_category:
        job.role_category = enrichment.role_category
    if enrichment.min_experience_years is not None and job.experience_min is None:
        job.experience_min = enrichment.min_experience_years
    if enrichment.max_experience_years is not None and job.experience_max is None:
        job.experience_max = enrichment.max_experience_years

    # Store full AI enrichment under raw_data['ai_enrichment']
    raw = dict(job.raw_data or {})
    raw["ai_enrichment"] = enrichment.model_dump()
    job.raw_data = raw

    await db.commit()
    await db.refresh(job)
    return enrichment
