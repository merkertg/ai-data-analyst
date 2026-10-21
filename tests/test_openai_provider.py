"""The OpenAI provider with a fake SDK: request shape, parsing, safe errors.

No network: the SDK factory is replaced, so these tests need no key.
"""

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.agents.schemas import AnalysisReport
from app.agents.tools import TOOL_DEFINITIONS
from app.llm.config import LLMSettings
from app.llm.errors import (
    LLMConfigurationError,
    LLMError,
    LLMInvalidResponseError,
    LLMRefusedError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.openai_provider import OpenAIProvider

SECRET = "sk-test-not-a-real-key"
REPORT = AnalysisReport(
    language="en",
    summary="Nothing to report.",
    facts=[],
    hypotheses=[],
    recommendations=[],
    limitations=["No data."],
)
REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")


class Item(SimpleNamespace):
    """An output item with the SDK's model_dump()."""

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {key: value for key, value in vars(self).items() if key != "content"} | (
            {"content": []} if "content" in vars(self) else {}
        )


def function_call(call_id: str = "call_1") -> Item:
    return Item(
        type="function_call",
        call_id=call_id,
        name="get_revenue",
        arguments='{"start": "2026-09-01", "end": "2026-10-01"}',
    )


def message(*parts: Any) -> Item:
    return Item(type="message", role="assistant", content=list(parts))


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="output_text", text=value)


def response(*items: Item, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        error=None,
        model="gpt-test-2026",
        output=list(items),
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
    )


class FakeSDK:
    """Record client options and the request; return or raise as told."""

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.options: dict[str, Any] = {}
        self.request: dict[str, Any] = {}
        self.responses = SimpleNamespace(create=self.create)

    def __call__(self, **options: Any) -> "FakeSDK":
        self.options = options
        return self

    def __enter__(self) -> "FakeSDK":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def create(self, **request: Any) -> Any:
        self.request = request
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def settings(**values: Any) -> LLMSettings:
    """OpenAI settings without reading the developer's .env."""
    defaults = {
        "llm_provider": "openai",
        "openai_api_key": SECRET,
        "openai_model": "gpt-test",
    }
    return LLMSettings(_env_file=None, **(defaults | values))


def provider(sdk: FakeSDK) -> OpenAIProvider:
    return OpenAIProvider(settings(), sdk_factory=sdk)  # type: ignore[arg-type]


def test_request_is_stateless_strict_and_bounded() -> None:
    """Fixed URL, no retries, store=False, strict report schema, our tools."""
    sdk = FakeSDK(response(function_call()))

    provider(sdk).next_turn([{"role": "user", "content": "q"}], TOOL_DEFINITIONS, 7.5)

    assert sdk.options["base_url"] == "https://api.openai.com/v1"
    assert sdk.options["max_retries"] == 0
    assert sdk.options["timeout"] == 7.5
    assert sdk.request["model"] == "gpt-test"
    assert sdk.request["store"] is False
    assert sdk.request["tools"] is TOOL_DEFINITIONS
    assert sdk.request["parallel_tool_calls"] is True
    text_format = sdk.request["text"]["format"]
    assert (text_format["type"], text_format["strict"]) == ("json_schema", True)
    assert "IndustrialFlow" in sdk.request["instructions"]


def test_function_calls_are_parsed() -> None:
    """Calls keep their raw JSON arguments for server-side validation."""
    turn = provider(
        FakeSDK(response(function_call("a"), function_call("b")))
    ).next_turn([], [], 10)

    assert [call.call_id for call in turn.calls] == ["a", "b"]
    assert turn.calls[0].arguments.startswith('{"start"')
    assert turn.report is None
    assert turn.usage is not None and turn.usage.total_tokens == 120
    assert turn.output_items[0]["type"] == "function_call"


def test_report_message_is_validated() -> None:
    """The final message must match AnalysisReport exactly."""
    turn = provider(
        FakeSDK(response(message(text(REPORT.model_dump_json()))))
    ).next_turn([], [], 10)

    assert turn.report == REPORT
    assert turn.calls == []


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        (response(message(text('{"summary": "no facts"}'))), LLMInvalidResponseError),
        (response(message(SimpleNamespace(type="refusal"))), LLMRefusedError),
        (
            response(function_call(), message(text(REPORT.model_dump_json()))),
            LLMInvalidResponseError,
        ),
        (response(), LLMInvalidResponseError),
        (response(function_call(), status="incomplete"), LLMInvalidResponseError),
        (openai.APITimeoutError(request=REQUEST), LLMTimeoutError),
        (
            openai.AuthenticationError(
                f"bad key {SECRET}",
                response=httpx2.Response(401, request=REQUEST),
                body=None,
            ),
            LLMConfigurationError,
        ),
        (
            openai.RateLimitError(
                "slow down", response=httpx2.Response(429, request=REQUEST), body=None
            ),
            LLMUnavailableError,
        ),
        (openai.APIConnectionError(request=REQUEST), LLMUnavailableError),
    ],
    ids=[
        "schema mismatch",
        "refusal",
        "calls and report",
        "empty",
        "incomplete",
        "timeout",
        "bad key",
        "rate limit",
        "network",
    ],
)
def test_failures_become_safe_errors(answer: Any, error: type[LLMError]) -> None:
    """The client sees a fixed message; SDK text and the key never leak."""
    with pytest.raises(error) as raised:
        provider(FakeSDK(answer)).next_turn([], [], 10)

    assert SECRET not in str(raised.value)
    assert raised.value.__cause__ is None


@pytest.mark.parametrize(
    "values", [{"openai_api_key": None}, {"openai_model": " "}], ids=["key", "model"]
)
def test_key_and_model_are_required(values: dict[str, Any]) -> None:
    """There is no default paid model and no implicit key."""
    with pytest.raises(LLMConfigurationError):
        OpenAIProvider(settings(**values))


def test_key_is_hidden_in_settings() -> None:
    """SecretStr and repr=False keep the key out of logs and errors."""
    assert SECRET not in repr(settings())
    assert SECRET not in str(settings().model_dump())
