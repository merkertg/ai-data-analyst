"""The final report: facts, hypotheses, recommendations and their evidence.

The model fills this schema through structured outputs. Every fact points at
exact values in tool results; the runtime checks those pointers before the
report is accepted (app.agents.evidence).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """No unknown fields: the JSON Schema gets additionalProperties: false."""

    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    """One exact value from one successful tool call of the same run."""

    call_id: str = Field(
        min_length=1,
        max_length=200,
        description="call_id of a successful tool call in this run",
    )
    field: str = Field(
        min_length=1,
        max_length=200,
        description="Dotted path inside the tool data, e.g. net_revenue.absolute "
        "or contributions.0.delta",
    )
    value: str = Field(
        max_length=200,
        description="The value at that path exactly as returned, as text",
    )


class Fact(_Strict):
    """A statement proven by tool results; its numbers come from evidence."""

    statement: str = Field(min_length=1, max_length=600)
    evidence: list[Evidence] = Field(max_length=8)


class Hypothesis(_Strict):
    """A possible explanation that the data suggests but does not prove."""

    statement: str = Field(min_length=1, max_length=600)
    evidence: list[Evidence] = Field(max_length=8)


class AnalysisReport(_Strict):
    """What the analyst returns: a short answer and separated reasoning parts.

    Every field is required (strict structured outputs); an empty list is the
    explicit way to say "none".
    """

    language: Literal["ru", "en"] = Field(description="Language of the user's question")
    summary: str = Field(min_length=1, max_length=1500)
    facts: list[Fact] = Field(max_length=12)
    hypotheses: list[Hypothesis] = Field(max_length=6)
    recommendations: list[str] = Field(max_length=6)
    limitations: list[str] = Field(max_length=6)


# OpenAI strict mode supports only part of JSON Schema. Length limits stay in
# Pydantic, which validates every answer after it arrives.
_UNSUPPORTED = {"minLength", "maxLength", "title", "default"}


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema of a model without keywords that strict mode rejects."""

    def clean(node: Any, field_names: bool = False) -> Any:
        if isinstance(node, dict):
            # Keys of "properties" are field names, not keywords: keep them all.
            return {
                key: clean(value, field_names=key == "properties" and not field_names)
                for key, value in node.items()
                if field_names or key not in _UNSUPPORTED
            }
        if isinstance(node, list):
            return [clean(item) for item in node]
        return node

    schema = clean(model.model_json_schema())
    assert isinstance(schema, dict)
    return schema
