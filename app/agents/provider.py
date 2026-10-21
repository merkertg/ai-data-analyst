"""Choose the provider from settings: mock by default, OpenAI only on request."""

from app.agents.contracts import AgentProvider
from app.agents.mock import MockProvider
from app.llm.config import LLMSettings
from app.llm.openai_provider import OpenAIProvider


def get_agent_provider(settings: LLMSettings) -> AgentProvider:
    """The mock needs nothing; OpenAI needs an explicit key and model."""
    if settings.llm_provider == "mock":
        return MockProvider()
    return OpenAIProvider(settings)
