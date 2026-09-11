from fastapi import APIRouter
from app.config import settings
from app.intelligence.llm_provider import get_llm_provider

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/llm")
async def llm_health():
    """Diagnose the currently active system AI provider."""
    provider = get_llm_provider()
    diag = await provider.test_connection()
    return {
        "provider": diag.get("provider", settings.LLM_PROVIDER),
        "model": diag.get("model", getattr(provider, "model", "default")),
        "reachable": diag.get("reachable", False),
        "latency_ms": diag.get("latency_ms"),
        "error": diag.get("error"),
    }