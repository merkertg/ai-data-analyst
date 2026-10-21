"""OpenAI Responses API: function calling plus a strict JSON report schema.

Each request sends the history, including encrypted reasoning items, instead
of using a stored response as continuation state. store=False controls response
storage; it does not establish provider-wide data retention guarantees.
"""

import json
from collections.abc import Callable
from typing import Any, cast

import openai
from pydantic import ValidationError

from app.agents.contracts import AgentTurn, ProviderName, TokenUsage, ToolCall
from app.agents.prompts import SYSTEM_PROMPT
from app.agents.schemas import AnalysisReport, strict_schema
from app.llm.config import LLMSettings
from app.llm.errors import (
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMRefusedError,
    LLMTimeoutError,
    LLMUnavailableError,
)

REPORT_FORMAT = {
    "type": "json_schema",
    "name": "analysis_report",
    "strict": True,
    "schema": strict_schema(AnalysisReport),
}


class OpenAIProvider:
    """One Responses API request per turn, without retries or stored state."""

    provider: ProviderName = "openai"

    def __init__(
        self,
        settings: LLMSettings,
        *,
        sdk_factory: Callable[..., openai.OpenAI] = openai.OpenAI,
    ) -> None:
        """Check that a key and a model are set; no network call happens here."""
        if settings.openai_api_key is None or settings.openai_model is None:
            raise LLMConfigurationError()
        self.model = settings.openai_model
        self._settings = settings
        self._sdk_factory = sdk_factory

    def next_turn(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        remaining_seconds: float,
    ) -> AgentTurn:
        """Send the history; return tool calls or a schema-valid report."""
        settings = self._settings
        assert settings.openai_api_key is not None
        try:
            with self._sdk_factory(
                api_key=settings.openai_api_key.get_secret_value(),
                # Fixed address: a base URL from the environment could send
                # the key and the data to another server.
                base_url="https://api.openai.com/v1",
                timeout=min(settings.llm_timeout_seconds, remaining_seconds),
                max_retries=0,
            ) as sdk:
                response = sdk.responses.create(
                    model=self.model,
                    instructions=SYSTEM_PROMPT,
                    # Plain JSON items; the SDK's TypedDicts describe the same shape.
                    input=cast(Any, history),
                    tools=cast(Any, tools),
                    tool_choice="auto",
                    parallel_tool_calls=True,
                    text=cast(Any, {"format": REPORT_FORMAT}),
                    max_output_tokens=settings.llm_max_output_tokens,
                    include=["reasoning.encrypted_content"],
                    store=False,
                    truncation="disabled",
                )
            return self._turn(response)
        except openai.APITimeoutError:
            raise LLMTimeoutError() from None
        except (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.NotFoundError,
            openai.BadRequestError,
        ):
            # A wrong key, an unknown model or an unsupported parameter.
            raise LLMConfigurationError() from None
        except openai.ContentFilterFinishReasonError:
            raise LLMRefusedError() from None
        except (
            openai.LengthFinishReasonError,
            openai.APIResponseValidationError,
            ValidationError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ):
            raise LLMInvalidResponseError() from None
        except openai.APIError:
            raise LLMUnavailableError() from None

    def _turn(self, response: Any) -> AgentTurn:
        """Accept tool calls or one report; anything else is invalid."""
        if response.status != "completed" or response.error is not None:
            raise LLMInvalidResponseError()
        if not response.model:
            raise LLMInvalidResponseError()
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        for item in response.output:
            if item.type == "function_call":
                calls.append(ToolCall(item.call_id, item.name, item.arguments))
            elif item.type == "message":
                for part in item.content:
                    if part.type == "refusal":
                        raise LLMRefusedError()
                    if part.type != "output_text":
                        raise LLMInvalidResponseError()
                    text_parts.append(part.text)
            elif item.type != "reasoning":
                raise LLMInvalidResponseError()
        report = None
        if text_parts:
            report = AnalysisReport.model_validate_json("".join(text_parts))
        if bool(calls) == (report is not None):
            raise LLMInvalidResponseError()
        usage = None
        if response.usage is not None:
            usage = TokenUsage(
                response.usage.input_tokens,
                response.usage.output_tokens,
                response.usage.total_tokens,
            )
        return AgentTurn(
            output_items=[
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            ],
            calls=calls,
            report=report,
            model=response.model,
            usage=usage,
        )
