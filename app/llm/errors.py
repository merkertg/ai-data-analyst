"""Expected agent failures with a fixed HTTP status and a public message.

Errors never carry the original SDK exception, the prompt or the key: the
message shown to the client is the class attribute, nothing else.
"""


class LLMError(Exception):
    """Base class: a safe status code, a stable code and a public message."""

    status_code = 503
    code = "llm_error"
    detail = "The AI analyst is temporarily unavailable."

    def __init__(self) -> None:
        """Ignore the cause on purpose; it may contain secrets or user data."""
        super().__init__(self.detail)


class LLMConfigurationError(LLMError):
    """Provider, key, model or limits are missing or invalid."""

    code = "configuration"
    detail = "Check the LLM settings: provider, key, model and limits."


class LLMUnavailableError(LLMError):
    """Network error, rate limit or provider outage."""

    code = "provider_unavailable"
    detail = "The LLM provider is unavailable. Try again later."


class LLMTimeoutError(LLMError):
    """The provider did not answer within the remaining time budget."""

    status_code = 504
    code = "provider_timeout"
    detail = "The LLM provider did not answer in time."


class LLMInvalidResponseError(LLMError):
    """An incomplete answer or one that does not match the strict schema."""

    status_code = 502
    code = "invalid_response"
    detail = "The LLM provider returned an incomplete or invalid answer."


class LLMRefusedError(LLMError):
    """The model refused; its own text is not published."""

    status_code = 502
    code = "refused"
    detail = "The LLM provider refused to answer."


class AgentStepLimitError(LLMError):
    """No valid report within the allowed number of model turns."""

    status_code = 502
    code = "step_limit"
    detail = "The agent reached its step limit without a verified report."


class AgentToolLimitError(LLMError):
    """A batch of calls would exceed the total tool call budget."""

    status_code = 502
    code = "tool_limit"
    detail = "The agent requested more tool calls than allowed."


class AgentInvalidTurnError(LLMError):
    """A turn with both or neither calls and report, or a repeated call id."""

    status_code = 502
    code = "invalid_turn"
    detail = "The agent received an invalid sequence of model answers."


class AgentUnverifiedReportError(LLMError):
    """The report still cites missing evidence after all corrections."""

    status_code = 502
    code = "unverified_report"
    detail = "The agent could not support its report with tool results."


class AgentContextTooLongError(LLMError):
    """The full transcript would exceed the context limit."""

    status_code = 413
    code = "context_too_long"
    detail = "The analysis needs more context than allowed."


class AgentTimeoutError(LLMError):
    """The whole run, model and tools together, ran out of time."""

    status_code = 504
    code = "timeout"
    detail = "The agent did not finish in time."


class ToolDataUnavailable(LLMError):
    """The database failed during a tool call; the run cannot continue."""

    code = "data_unavailable"
    detail = "Analytics data is temporarily unavailable."
