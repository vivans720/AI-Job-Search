import json
import time
from typing import Any, AsyncIterator
import structlog
from pydantic import BaseModel

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.language_models.chat_models import BaseChatModel

from app.intelligence.base import BaseAIProvider, clean_and_extract_json
from app.intelligence.models import (
    AIModel,
    ProviderCapabilities,
    StreamCompleted,
    StreamError,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallResult,
    ToolDefinition,
    UsageEvent,
)

logger = structlog.get_logger(__name__)


def convert_messages_to_langchain(messages: list[dict[str, str]]) -> list[BaseMessage]:
    """Translates dictionary-based chat message structures into LangChain BaseMessage objects."""
    lc_messages: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role in ("assistant", "ai"):
            lc_messages.append(AIMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        else:
            lc_messages.append(ChatMessage(role=role, content=content))
    return lc_messages


class LangChainAIProvider(BaseAIProvider):
    """Unified integration adapter that wraps any LangChain BaseChatModel instance
    into the application's clean BaseAIProvider domain abstraction.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        provider_name: str,
        model: str,
        capabilities: ProviderCapabilities | None = None,
    ):
        self.llm = llm
        self.provider_name = provider_name
        self.model = model
        self._capabilities = capabilities or ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=False,
        )

    def get_capabilities(self, model: str | None = None) -> ProviderCapabilities:
        return self._capabilities

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        lc_msgs = convert_messages_to_langchain(messages)
        call_kwargs = dict(kwargs)
        # Normalize token limit parameter across provider implementations
        if "max_tokens" in call_kwargs:
            val = call_kwargs.pop("max_tokens")
            if self.provider_name == "ollama":
                call_kwargs["num_predict"] = val
            elif self.provider_name == "gemini":
                call_kwargs["max_output_tokens"] = val
            else:
                call_kwargs["max_tokens"] = val

        try:
            response = await self.llm.ainvoke(lc_msgs, **call_kwargs)
            if isinstance(response.content, str):
                return response.content.strip()
            if isinstance(response.content, list):
                parts = []
                for p in response.content:
                    if isinstance(p, dict) and "text" in p:
                        parts.append(p["text"])
                    elif isinstance(p, str):
                        parts.append(p)
                return "".join(parts).strip()
            return str(response.content).strip()
        except Exception as e:
            logger.error("langchain_complete_failed", provider=self.provider_name, model=self.model, error=str(e))
            raise

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Runs structured JSON output via LangChain with_structured_output when schema provided,
        falling back to text completion and robust JSON extraction.
        """
        if schema is not None and isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                structured_model = self.llm.with_structured_output(schema)
                lc_msgs = convert_messages_to_langchain(messages)
                result = await structured_model.ainvoke(lc_msgs, **kwargs)
                if isinstance(result, BaseModel):
                    return result.model_dump()
                if isinstance(result, dict):
                    return result
            except Exception as e:
                logger.warning(
                    "langchain_structured_output_failed_fallback_to_json",
                    provider=self.provider_name,
                    error=str(e),
                )

        augmented_messages = list(messages)
        augmented_messages.append({
            "role": "user",
            "content": "Ensure the response is valid, parsable JSON without markdown fences or preamble.",
        })
        text = await self.complete(augmented_messages, **kwargs)
        return clean_and_extract_json(text)

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[StreamEvent]:
        lc_msgs = convert_messages_to_langchain(messages)
        try:
            async for chunk in self.llm.astream(lc_msgs, **kwargs):
                content = chunk.content
                text_piece = ""
                if isinstance(content, str):
                    text_piece = content
                elif isinstance(content, list):
                    parts = []
                    for p in content:
                        if isinstance(p, dict) and "text" in p:
                            parts.append(p["text"])
                        elif isinstance(p, str):
                            parts.append(p)
                    text_piece = "".join(parts)

                if text_piece:
                    yield TextDelta(text=text_piece)

                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    yield UsageEvent(
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                        total_tokens=usage.get("total_tokens"),
                    )

            yield StreamCompleted(finish_reason="stop")
        except Exception as e:
            logger.error("langchain_stream_failed", provider=self.provider_name, error=str(e))
            yield StreamError(error=str(e))

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolDefinition | dict[str, Any]],
        **kwargs: Any,
    ) -> ToolCallResult:
        lc_msgs = convert_messages_to_langchain(messages)
        formatted_tools = []
        for t in tools:
            if isinstance(t, ToolDefinition):
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                })
            elif isinstance(t, dict) and "function" in t:
                formatted_tools.append(t)
            elif isinstance(t, dict) and "name" in t:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", t.get("input_schema", {})),
                    },
                })
            else:
                formatted_tools.append(t)

        try:
            tool_bound_llm = self.llm.bind_tools(formatted_tools)
            response = await tool_bound_llm.ainvoke(lc_msgs, **kwargs)

            content = response.content if isinstance(response.content, str) else ""
            parsed_tools: list[ToolCall] = []

            raw_tool_calls = getattr(response, "tool_calls", []) or []
            for tc in raw_tool_calls:
                parsed_tools.append(
                    ToolCall(
                        id=tc.get("id", f"call_{len(parsed_tools)}"),
                        name=tc.get("name", ""),
                        arguments=tc.get("args", {}),
                    )
                )

            usage = None
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                usage = {
                    "input_tokens": usage_meta.get("input_tokens", 0),
                    "output_tokens": usage_meta.get("output_tokens", 0),
                    "total_tokens": usage_meta.get("total_tokens", 0),
                }

            return ToolCallResult(
                content=content.strip(),
                tool_calls=parsed_tools,
                finish_reason="tool_calls" if parsed_tools else "stop",
                usage=usage,
            )
        except Exception as e:
            logger.error("langchain_tools_failed", provider=self.provider_name, error=str(e))
            raise
