from fastapi import APIRouter
from app.config import settings
from app.intelligence.llm_provider import get_llm_provider

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/llm")
async def llm_health():
    provider_name = settings.LLM_PROVIDER
    model = settings.OLLAMA_MODEL if provider_name == "ollama" else settings.LLM_MODEL

    try:
        provider = get_llm_provider()
        await provider.complete([{"role": "user", "content": "ping"}], max_tokens=5)
        return {
            "provider": provider_name,
            "model": model,
            "reachable": True,
        }
    except Exception as e:
        return {
            "provider": provider_name,
            "model": model,
            "reachable": False,
            "error": str(e),
        }