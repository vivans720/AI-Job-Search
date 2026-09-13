import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from app.intelligence.base import clean_and_extract_json
from app.intelligence.llm_provider import create_ai_provider, get_llm_provider, reset_ai_provider_cache
from app.intelligence.providers.ollama_provider import OllamaProvider
from app.intelligence.providers.openai_provider import OpenAIProvider
from app.intelligence.providers.gemini_provider import GeminiProvider
from app.intelligence.providers.anthropic_provider import AnthropicProvider
from app.intelligence.service import AIService


def test_clean_and_extract_json():
    # Markdown fenced json
    text1 = '```json\n{"skills": ["python", "fastapi"]}\n```'
    assert clean_and_extract_json(text1) == {"skills": ["python", "fastapi"]}

    # Surrounding conversational noise
    text2 = 'Here is the requested result:\n{"matched": true, "score": 95}\nHope this helps!'
    assert clean_and_extract_json(text2) == {"matched": True, "score": 95}

    # Plain json
    text3 = '{"status": "ok"}'
    assert clean_and_extract_json(text3) == {"status": "ok"}


def test_provider_factory_instances():
    p_ollama = create_ai_provider("ollama")
    assert isinstance(p_ollama, OllamaProvider)
    assert p_ollama.provider_name == "ollama"

    p_openai = create_ai_provider("openai")
    assert isinstance(p_openai, OpenAIProvider)
    assert p_openai.provider_name == "openai"

    p_gemini = create_ai_provider("gemini")
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.provider_name == "gemini"

    p_anthropic = create_ai_provider("anthropic")
    assert isinstance(p_anthropic, AnthropicProvider)
    assert p_anthropic.provider_name == "anthropic"

    p_custom = create_ai_provider("openai_compatible", base_url="http://custom:8000/v1")
    assert isinstance(p_custom, OpenAIProvider)
    assert p_custom.base_url == "http://custom:8000/v1"


@pytest.mark.asyncio
async def test_ollama_provider_complete_mocked():
    provider = OllamaProvider()
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content="Mocked Ollama reply")

        result = await provider.complete([{"role": "user", "content": "Hi"}])
        assert result == "Mocked Ollama reply"
        mock_invoke.assert_called_once()


@pytest.mark.asyncio
async def test_openai_provider_complete_json_mocked():
    provider = OpenAIProvider(api_key="sk-test-key")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content='{"roles": ["Backend Engineer"]}')

        data = await provider.complete_json([{"role": "user", "content": "Return roles"}])
        assert data == {"roles": ["Backend Engineer"]}


@pytest.mark.asyncio
async def test_ai_service_skill_gap_analysis():
    mock_provider = AsyncMock()
    mock_provider.complete_json.return_value = {
        "learning_roadmap": [{"skill": "Docker", "action": "Build container", "estimated_days": 2}],
        "interview_talking_points": ["Discuss virtualization principles"],
    }
    svc = AIService(provider=mock_provider)
    result = await svc.analyze_skill_gap(
        candidate_skills=["Python", "FastAPI"],
        job_required=["Python", "FastAPI", "Docker"],
        job_preferred=["AWS"],
    )
    assert "Docker" in result.missing_critical_skills
    assert "AWS" in result.missing_preferred_skills
    assert "Python" in result.matched_skills
    assert len(result.learning_roadmap) == 1


@pytest.mark.asyncio
async def test_gemini_test_connection_parameter_mapping():
    provider = GeminiProvider(api_key="mock-key")
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = AIMessage(content="ok")
        res = await provider.test_connection()
        assert res["reachable"] is True
        assert res["provider"] == "gemini"
        call_kwargs = mock_invoke.call_args.kwargs
        assert "max_output_tokens" in call_kwargs
        assert call_kwargs["max_output_tokens"] == 5
        assert "max_tokens" not in call_kwargs
