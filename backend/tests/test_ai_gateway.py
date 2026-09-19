import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from openai import InternalServerError, RateLimitError
import httpx
from langchain_core.messages import AIMessage

from app.intelligence.base import BaseAIProvider
from app.intelligence.models import (
    AIModel,
    ProviderCapabilities,
    ToolCall,
    ToolCallResult,
    ToolDefinition,
)
from app.intelligence.registry import ProviderRegistry
from app.intelligence.gateway import AIGateway
from app.intelligence.llm_provider import create_ai_provider, get_llm_provider
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider


def test_provider_registry_contains_omniroute_gateway():
    providers = ProviderRegistry.list_providers()
    provider_ids = {p.id for p in providers}
    assert "omniroute" in provider_ids
    metadata = ProviderRegistry.get_metadata("omniroute")
    assert metadata is not None
    assert metadata.name == "OmniRoute AI Gateway"


def test_resolve_model_reference():
    p, m = ProviderRegistry.resolve_model_reference("omniroute/meta-llama/llama-3.3-70b")
    assert p == "omniroute"
    assert m == "meta-llama/llama-3.3-70b"

    p, m = ProviderRegistry.resolve_model_reference("gpt-4o-mini")
    assert p == "omniroute"
    assert m == "gpt-4o-mini"


def test_provider_factory_adapters():
    omni = create_ai_provider("omniroute")
    assert isinstance(omni, OpenAICompatibleProvider)
    assert omni.provider_name == "omniroute"

    custom_model = create_ai_provider("omniroute", model="claude-3-5-sonnet")
    assert isinstance(custom_model, OpenAICompatibleProvider)
    assert custom_model.model == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_openai_compatible_complete_json_and_streaming():
    provider = OpenAICompatibleProvider(base_url="http://mock:8000/v1", api_key="test-key", model="test-m")
    mock_ai_msg = AIMessage(content='{"analysis": "strong", "rating": 90}')

    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_ai_msg
        data = await provider.complete_json([{"role": "user", "content": "analyze"}])
        assert data == {"analysis": "strong", "rating": 90}


@pytest.mark.asyncio
async def test_ai_gateway_transient_retry_success():
    primary = MagicMock(spec=BaseAIProvider)
    primary.provider_name = "omniroute"
    primary.model = "gpt-4o-mini"
    primary.get_capabilities.return_value = ProviderCapabilities()

    # Fail once with 429 rate limit, then succeed
    req = httpx.Request("POST", "http://test")
    resp = httpx.Response(429, request=req)
    primary.complete = AsyncMock(side_effect=[RateLimitError("Rate limit exceeded", response=resp, body=None), "Success response"])

    gateway = AIGateway(primary=primary, max_retries=2, initial_backoff=0.01)
    res = await gateway.complete([{"role": "user", "content": "hi"}])
    assert res == "Success response"
    assert primary.complete.call_count == 2


@pytest.mark.asyncio
async def test_ai_gateway_fallback_on_primary_outage():
    primary = MagicMock(spec=BaseAIProvider)
    primary.provider_name = "omniroute-primary"
    primary.model = "gpt-4o-mini"
    primary.get_capabilities.return_value = ProviderCapabilities()
    primary.complete = AsyncMock(side_effect=httpx.ConnectTimeout("Primary timeout"))

    fallback = MagicMock(spec=BaseAIProvider)
    fallback.provider_name = "omniroute-fallback"
    fallback.model = "gemini-2.0-flash"
    fallback.complete = AsyncMock(return_value="Fallback response")

    gateway = AIGateway(primary=primary, fallback=fallback, max_retries=1, initial_backoff=0.01)
    res = await gateway.complete([{"role": "user", "content": "ping"}])
    assert res == "Fallback response"
    assert fallback.complete.call_count == 1


@pytest.mark.asyncio
async def test_gateway_does_not_fallback_on_400_bad_request():
    primary = MagicMock(spec=BaseAIProvider)
    primary.provider_name = "omniroute"
    primary.model = "gpt-4o-mini"
    primary.get_capabilities.return_value = ProviderCapabilities()
    primary.complete = AsyncMock(side_effect=ValueError("Bad prompt format or invalid argument"))

    fallback = MagicMock(spec=BaseAIProvider)
    fallback.complete = AsyncMock(return_value="Should not be called")

    gateway = AIGateway(primary=primary, fallback=fallback, max_retries=1)
    with pytest.raises(ValueError):
        await gateway.complete([{"role": "user", "content": "bad input"}])
    assert fallback.complete.call_count == 0
