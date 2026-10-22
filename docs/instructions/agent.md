# AI analyst

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Ask questions in natural language; the agent calls read-only analytics tools and returns a report with checked evidence references and numeric literals. The detailed explanation in Russian is in the [Stage 07 guide](../STAGE_07.md), the design in [ADR 0007](../adr/0007-ai-agent-tool-calling.md).

## Start

Apply migrations (head is `0004`), load data, start the server and issue an **analyst** token as in the [quickstart](quickstart.md). The default provider is `mock`: real tools and checks, no language model, no key.

```bash
curl -i -X POST http://127.0.0.1:8000/api/agent/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question": "Why did revenue fall in September?"}'
```

## Use OpenAI

Set these values in `.env` (never commit it) and restart the server:

| Variable | Value |
| --- | --- |
| `LLM_PROVIDER` | `openai` (default `mock`) |
| `OPENAI_API_KEY` | Your key |
| `OPENAI_MODEL` | A model compatible with function calling, structured outputs and encrypted reasoning items; there is no default |

Without a key or a model, `POST /api/agent/runs` answers `503` and no run is stored.

The provider uses the official Responses API, replays the history with `store=False` and does not set `previous_response_id` or a server-side conversation. This does not establish a blanket provider no-retention policy. The adapter has been tested with a fake SDK; a real model request has not been verified.

## Limits

| Variable | Default | Range |
| --- | --- | --- |
| `AGENT_MAX_STEPS` | 8 | 1–12 model turns |
| `AGENT_MAX_TOOL_CALLS` | 16 | 1–32 tool calls per run |
| `AGENT_MAX_CORRECTIONS` | 2 | 0–3 report corrections |
| `AGENT_TIMEOUT_SECONDS` | 120 | 1–600, model and tools together |
| `LLM_TIMEOUT_SECONDS` | 60 | 1–300, one model request |
| `LLM_MAX_OUTPUT_TOKENS` | 4000 | 256–16000 |

The runtime checks its time budget between operations and bounds each model request by the remaining time. It does not cancel an in-flight synchronous SQL/tool operation at the deadline; the budget is not a hard HTTP response deadline. Tool arguments are capped at 2,000 JSON characters and results at 16,000 characters; an oversized result becomes a tool error. The transcript cap is 120,000 characters.

## Tools

`get_data_coverage`, `get_revenue`, `compare_periods`, `get_sales_by_category`, `get_sales_by_region`, `get_top_products`, `get_refund_statistics`, `detect_anomalies`, `get_inventory_history`. Periods are half-open Moscow dates of at most 24 months. The model cannot run SQL or change data.

## Response

`201 Created` with `location: /api/agent/runs/<uuid>`:

| Field | Meaning |
| --- | --- |
| `status` | `completed` for `201`; a stored failed run is readable through the history API |
| `report.summary` | Short answer in the question's language |
| `report.facts[].evidence[]` | `call_id`, `field` path and exact `value` from a tool result |
| `report.hypotheses`, `recommendations`, `limitations` | Separate lists; hypotheses are not proven causes |
| `tool_calls[]` | Processed calls, including rejected arguments or tool errors, with recorded arguments and results |
| `steps`, `corrections`, `usage`, `duration_ms` | How the run went |

A report is accepted only when every evidence value matches a successful tool result and recognised numeric literals match verified evidence by magnitude. Facts and hypotheses use their own evidence; the summary, recommendations and limitations use evidence from the whole report. ISO dates, calendar-context years, codes and cited names are excluded. Bare four-digit amounts and numbers followed by units still require evidence. This guard does not prove metric identity, sign, date correctness or causation; number words and other notation may not be recognised.

## History

```bash
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/agent/runs?limit=10"
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/agent/runs/<uuid>
```

Handled `LLMError` failures after a run starts are stored with the partial tool trace when the database write succeeds. Provider errors after startup can therefore return `503` with a `run_id`. Configuration errors before startup, SQL/tool availability failures and failed history writes do not have a reliable stored run. Unexpected exceptions are not automatically recorded as failed runs.

## Status codes

| Code | When |
| --- | --- |
| `201` | Verified report |
| `401` | Missing or invalid API token |
| `403` | The token has the viewer role; asking needs analyst |
| `429` | More than `AGENT_RUNS_PER_MINUTE` (default 6) runs for this token in a minute |
| `422` | Missing, blank or over-long question, or an extra field |
| `502` | Step or tool limit, invalid model answer or failed evidence check (`run_id` after a successful history write) |
| `503` | LLM settings missing, provider or database unavailable |
| `504` | The run or a model request ran out of time (`run_id` after a successful history write) |
| `413` | The transcript exceeded 120,000 characters (`run_id` after a successful history write) |
