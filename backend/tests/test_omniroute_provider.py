import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.messages import AIMessageChunk
from openai import AuthenticationError, APIConnectionError, APITimeoutError, InternalServerError

from app.config import settings
from app.intelligence.llm_provider import create_ai_provider, get_llm_provider, reset_ai_provider_cache
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider
from app.intelligence.registry import ProviderRegistry
from app.intelligence.gateway import AIGateway
from app.intelligence.service import AIService
from app.intelligence.extractors import enrich_job_record_llm


def test_omniroute_registered_in_registry():
    metadata = ProviderRegistry.get_metadata("omniroute")
    assert metadata is not None
    assert metadata.id == "omniroute"
    assert metadata.name == "OmniRoute AI Gateway"
    assert metadata.type == "cloud"
    assert metadata.capabilities.supports_streaming is True
    assert metadata.capabilities.supports_tools is True
    assert metadata.capabilities.supports_structured_output is True
    assert metadata.capabilities.supports_model_discovery is True


def test_create_omniroute_provider_default_config():
    provider = create_ai_provider("omniroute")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_name == "omniroute"
    assert provider.base_url == settings.OMNIROUTE_BASE_URL.rstrip("/")
    assert provider.model == settings.OMNIROUTE_MODEL
    assert provider.timeout == settings.OMNIROUTE_TIMEOUT


def test_create_omniroute_provider_custom_config():
    provider = create_ai_provider(
        provider_name="omniroute",
        base_url="http://omniroute.internal:9000/v1",
        api_key="omni-secret-key",
        model="claude-3-5-sonnet",
        timeout=60.0,
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_name == "omniroute"
    assert provider.base_url == "http://omniroute.internal:9000/v1"
    assert provider.model == "claude-3-5-sonnet"
    assert provider.timeout == 60.0


@pytest.mark.asyncio
async def test_omniroute_complete():
    provider = create_ai_provider("omniroute")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content="OmniRoute routed response successfully.")
        result = await provider.complete([{"role": "user", "content": "Hello"}])
        assert result == "OmniRoute routed response successfully."
        mock_invoke.assert_called_once()


@pytest.mark.asyncio
async def test_omniroute_complete_json():
    provider = create_ai_provider("omniroute")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content='{"status": "success", "candidate": "Jane Doe"}')
        result = await provider.complete_json([{"role": "user", "content": "Extract"}])
        assert result == {"status": "success", "candidate": "Jane Doe"}


@pytest.mark.asyncio
async def test_omniroute_stream():
    provider = create_ai_provider("omniroute")

    async def mock_astream(*args, **kwargs):
        chunks = ["Hello", " world", " from OmniRoute!"]
        for c in chunks:
            yield AIMessageChunk(content=c)

    with patch.object(type(provider.llm), "astream", side_effect=mock_astream):
        events = []
        async for evt in provider.stream([{"role": "user", "content": "Stream test"}]):
            events.append(evt)

        assert len(events) >= 3
        text_received = "".join([e.text for e in events if hasattr(e, "text") and e.text])
        assert text_received == "Hello world from OmniRoute!"


@pytest.mark.asyncio
async def test_omniroute_test_connection_success():
    provider = create_ai_provider("omniroute")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content="ok")
        diag = await provider.test_connection()
        assert diag["reachable"] is True
        assert diag["provider"] == "omniroute"
        assert diag["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_omniroute_test_connection_failure():
    provider = create_ai_provider("omniroute")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Connection refused to OmniRoute port 8000")
        diag = await provider.test_connection()
        assert diag["reachable"] is False
        assert diag["provider"] == "omniroute"
        assert "Connection refused" in diag["error"]


@pytest.mark.asyncio
async def test_omniroute_candidate_profile_extraction_via_service():
    provider = create_ai_provider("omniroute")
    mock_resume_json = {
        "candidate_name": "Alice Developer",
        "email": "alice@example.com",
        "experience_level": "MID",
        "experience_years": 4,
        "target_roles": ["Backend Engineer"],
        "programming_languages": ["Python", "Go"],
        "frameworks": ["FastAPI"],
        "databases": ["PostgreSQL"],
        "cloud": ["AWS"],
        "tools": ["Docker", "Git"],
        "skills": ["REST APIs"],
        "education": [],
        "projects": [],
        "work_experience": [],
        "certifications": [],
        "preferred_locations": ["Bengaluru"],
        "summary": "Experienced backend developer."
    }

    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        import json
        mock_invoke.return_value = AIMessage(content=json.dumps(mock_resume_json))
        ai_service = AIService(provider=provider)
        extracted = await ai_service.extract_candidate_profile("Sample resume text for Alice")

        assert extracted.candidate_name == "Alice Developer"
        assert extracted.experience_years == 4
        assert "Python" in extracted.programming_languages


@pytest.mark.asyncio
async def test_omniroute_job_enrichment_via_service():
    provider = create_ai_provider("omniroute")
    mock_enrich_json = {
        "standardized_title": "Senior Python Developer",
        "role_category": "BACKEND",
        "seniority": "SENIOR",
        "min_experience_years": 5,
        "max_experience_years": 8,
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Kubernetes"],
        "core_responsibilities": ["Build scalable microservices"],
        "requirements_summary": ["Strong Python experience"],
        "tech_stack": ["Python", "FastAPI", "Docker"],
        "remote_policy_reasoning": "Standard remote policy."
    }

    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        import json
        mock_invoke.return_value = AIMessage(content=json.dumps(mock_enrich_json))
        ai_service = AIService(provider=provider)
        res = await ai_service.enrich_job(
            title="Senior Python Developer",
            description="We need a Python developer with FastAPI and Kubernetes experience in Bengaluru."
        )
        assert res.standardized_title == "Senior Python Developer"
        assert res.role_category == "BACKEND"
        assert "Python" in res.required_skills


@pytest.mark.asyncio
async def test_omniroute_with_gateway_resilience_and_error_handling():
    # Verify OmniRoute as primary within AIGateway with transient retry
    primary = create_ai_provider("omniroute")
    gateway = AIGateway(primary=primary, max_retries=1, initial_backoff=0.01)

    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise APITimeoutError(request=MagicMock())
        return AIMessage(content="Recovered after retry")

    with patch.object(type(primary.llm), "ainvoke", side_effect=flaky_ainvoke):
        resp = await gateway.complete([{"role": "user", "content": "Test"}])
        assert resp == "Recovered after retry"
        assert call_count == 2
