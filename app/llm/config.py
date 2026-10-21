"""LLM and agent settings, separate from the database settings.

A wrong key or model must not break /health, /ready or the analytics routes,
so these values are read only when the agent actually runs.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm.errors import LLMConfigurationError


class LLMSettings(BaseSettings):
    """Provider, model and the limits that bound one agent run."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # The key must never appear in a validation error message.
        hide_input_in_errors=True,
    )

    # "mock" needs no key and no network: a deterministic demo planner.
    llm_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    # No default model: a paid model is always an explicit choice.
    openai_model: str | None = Field(default=None, max_length=200)
    llm_timeout_seconds: float = Field(default=60, ge=1, le=300, allow_inf_nan=False)
    llm_max_output_tokens: int = Field(default=4000, ge=256, le=16000)

    # One run: model turns, tool calls, report corrections and total time.
    agent_max_steps: int = Field(default=8, ge=1, le=12)
    agent_max_tool_calls: int = Field(default=16, ge=1, le=32)
    agent_max_corrections: int = Field(default=2, ge=0, le=3)
    agent_timeout_seconds: float = Field(default=120, ge=1, le=600, allow_inf_nan=False)

    @field_validator("openai_api_key", "openai_model", mode="before")
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        """Treat an empty or whitespace value in .env as not configured."""
        if isinstance(value, str):
            return value.strip() or None
        return value


@lru_cache
def get_llm_settings() -> LLMSettings:
    """Read the settings once; a broken .env becomes a safe 503 error."""
    try:
        return LLMSettings()
    except ValidationError:
        raise LLMConfigurationError() from None
