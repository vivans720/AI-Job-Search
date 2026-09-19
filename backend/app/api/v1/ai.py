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
    requires_api_key: bool = True
    base_url: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)




class EnrichJobRequest(BaseModel):
    title: str
    description: str


@router.get("/providers", response_model=list[AIProviderInfo])
async def list_ai_providers(db: AsyncSession = Depends(get_db)):
    """List supported AI gateway (OmniRoute) with capability metadata and configuration status."""
    from app.intelligence.registry import ProviderRegistry

    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)

    def is_configured(pid: str) -> bool:
        return bool(settings.OMNIROUTE_BASE_URL or pref.ai_base_url)

    registered = ProviderRegistry.list_providers()
    res: list[AIProviderInfo] = []
    for p in registered:
        res.append(
            AIProviderInfo(
                id=p.id,
                name=p.name,
                type=p.type,
                default_model=pref.ai_model or settings.DEFAULT_AGENT_MODEL or p.default_model,
                configured=is_configured(p.id),
                description=p.description,
                requires_api_key=p.requires_api_key,
                base_url=pref.ai_base_url or settings.OMNIROUTE_BASE_URL,
                capabilities=p.capabilities.model_dump(),
            )
        )
    return res


@router.get("/models")
async def list_provider_models(provider: str | None = None, db: AsyncSession = Depends(get_db)):
    """List available models for a given provider or active provider."""
    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)

    target_provider = provider or pref.ai_provider or settings.LLM_PROVIDER
    try:
        p_instance = create_ai_provider(
            provider_name=target_provider,
            base_url=pref.ai_base_url if pref.ai_provider == target_provider else None,
            api_key=pref.ai_api_key if pref.ai_provider == target_provider else None,
        )
        models = await p_instance.list_models()
        return {"provider": target_provider, "models": [m.model_dump() for m in models]}
    except Exception as e:
        return {"provider": target_provider, "models": [], "error": str(e)}


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


# =====================================================================
# Phase 41 — AI Evaluation Framework Endpoints
# =====================================================================

class RunEvaluationRequest(BaseModel):
    category: str = "all"  # "all" | "resumes" | "jobs"


@router.post("/evaluation/run")
async def run_evaluation_suite(req: RunEvaluationRequest):
    """Phase 41: Runs AI evaluation benchmark across ground-truth fixtures and returns report."""
    from app.intelligence.evaluation.runner import EvaluationRunner

    runner = EvaluationRunner()
    report = await runner.run_evaluation(category=req.category)
    runner.save_report(report)
    return report


@router.get("/evaluation/report")
async def get_latest_evaluation_report():
    """Phase 41: Retrieves the latest evaluation benchmark report."""
    from pathlib import Path
    import json

    report_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "eval_reports" / "latest_eval.json"
    if not report_path.exists():
        return {
            "status": "not_run",
            "message": "No evaluation run recorded yet. Call POST /api/v1/ai/evaluation/run to benchmark.",
        }
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read evaluation report: {e}")

