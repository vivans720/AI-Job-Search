import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.intelligence.llm_provider import create_ai_provider, get_llm_provider
from app.intelligence.service import AIService
from app.intelligence.extractors import enrich_job_record_llm
from app.intelligence.schemas import (
    CandidateProfileOutput,
    JobSkillsOutput,
    SkillNormalizationOutput,
    JobEnrichmentOutput,
)
from app.services.preference_service import get_or_create_preferences
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/ai", tags=["AI Provider & Pipeline"])


class AIConnectionTestRequest(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class AIProviderInfo(BaseModel):
    id: str
    name: str
    type: str  # "local" | "cloud"
    default_model: str
    configured: bool
    description: str


class JobSkillsExtractRequest(BaseModel):
    title: str
    description: str


class NormalizeSkillsRequest(BaseModel):
    skills: list[str]


class EnrichJobRequest(BaseModel):
    title: str
    description: str


@router.get("/providers", response_model=list[AIProviderInfo])
async def list_ai_providers(db: AsyncSession = Depends(get_db)):
    """List supported AI providers and their configuration status."""
    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)

    active_provider = (pref.ai_provider or settings.LLM_PROVIDER).lower()

    providers = [
        AIProviderInfo(
            id="ollama",
            name="Ollama (Local LLM)",
            type="local",
            default_model=pref.ai_model or settings.OLLAMA_MODEL,
            configured=True,
            description="Runs locally on your machine with zero cloud cost and full privacy (default: qwen3.5:9b).",
        ),
        AIProviderInfo(
            id="openai",
            name="OpenAI",
            type="cloud",
            default_model=settings.OPENAI_MODEL,
            configured=bool(settings.OPENAI_API_KEY or (pref.ai_provider == "openai" and pref.ai_api_key)),
            description="OpenAI official API (GPT-4o, GPT-4o-mini). High accuracy structured outputs.",
        ),
        AIProviderInfo(
            id="gemini",
            name="Google Gemini",
            type="cloud",
            default_model=settings.GEMINI_MODEL,
            configured=bool(settings.GEMINI_API_KEY or (pref.ai_provider == "gemini" and pref.ai_api_key)),
            description="Google Gemini via OpenAI-compatible endpoint (gemini-2.0-flash). Fast and cost-efficient.",
        ),
        AIProviderInfo(
            id="anthropic",
            name="Anthropic Claude",
            type="cloud",
            default_model=settings.ANTHROPIC_MODEL,
            configured=bool(settings.ANTHROPIC_API_KEY or (pref.ai_provider == "anthropic" and pref.ai_api_key)),
            description="Anthropic Claude 3.5 Haiku / Sonnet via Messages API. Superior reasoning.",
        ),
        AIProviderInfo(
            id="deepseek",
            name="DeepSeek",
            type="cloud",
            default_model=settings.DEEPSEEK_MODEL,
            configured=bool(settings.DEEPSEEK_API_KEY or (pref.ai_provider == "deepseek" and pref.ai_api_key)),
            description="DeepSeek V3 / R1 reasoning and chat API.",
        ),
        AIProviderInfo(
            id="openai_compatible",
            name="Custom / OmniRoute Proxy",
            type="cloud",
            default_model=settings.LLM_MODEL,
            configured=bool(settings.LLM_BASE_URL),
            description="Any OpenAI-compatible server (OmniRoute, vLLM, LM Studio, OpenRouter).",
        ),
    ]
    return providers


@router.post("/test")
async def test_ai_connection(
    req: AIConnectionTestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Test connection and measure latency for a given provider configuration."""
    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)

    api_key = req.api_key
    if not api_key and pref.ai_provider == req.provider:
        api_key = pref.ai_api_key

    try:
        provider = create_ai_provider(
            provider_name=req.provider,
            model=req.model,
            base_url=req.base_url,
            api_key=api_key,
            timeout=15.0,
        )
        return await provider.test_connection()
    except Exception as e:
        return {
            "provider": req.provider,
            "model": req.model,
            "reachable": False,
            "latency_ms": 0,
            "error": str(e),
        }


# =====================================================================
# Phase 40 — AI Pipeline Endpoints
# =====================================================================

@router.post("/pipeline/extract-job-skills", response_model=JobSkillsOutput)
async def extract_job_skills_endpoint(req: JobSkillsExtractRequest):
    """Phase 40: Extracts required vs preferred skills and tech stack from job posting."""
    service = AIService()
    return await service.extract_job_skills(req.title, req.description)


@router.post("/pipeline/normalize-skills", response_model=SkillNormalizationOutput)
async def normalize_skills_endpoint(req: NormalizeSkillsRequest):
    """Phase 40: Standardizes ambiguous/variant skills into canonical industry names."""
    service = AIService()
    return await service.normalize_skills_llm(req.skills)


@router.post("/pipeline/enrich-job", response_model=JobEnrichmentOutput)
async def enrich_job_endpoint(req: EnrichJobRequest):
    """Phase 40: Deep intelligence enrichment on job title and description."""
    service = AIService()
    return await service.enrich_job(req.title, req.description)


@router.post("/pipeline/enrich-job-record/{job_id}", response_model=JobEnrichmentOutput)
async def enrich_stored_job_record(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Phase 40: Runs AI enrichment for an existing stored Job and updates database."""
    enriched = await enrich_job_record_llm(job_id=job_id, db=db)
    if not enriched:
        raise HTTPException(status_code=404, detail="Job not found")
    return enriched
