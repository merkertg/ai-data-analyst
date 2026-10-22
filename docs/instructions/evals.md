# Agent evals

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Measure the AI analyst on 42 questions whose answers are computed independently from the CSV bundle. Method and results are in [Evaluation](../EVALUATION.md); the Russian walkthrough is in the [Stage 09 guide](../STAGE_09.md).

## Prepare a database

The database must contain exactly the bundle the oracle reads. Use a dedicated `_test` database, never your working data:

```bash
uv run python -m app.data.generate --output data/demo
export DATABASE_URL='postgresql+psycopg://analyst:analyst_test@127.0.0.1:5437/industrialflow_demo_test'
uv run alembic upgrade head
uv run python -m app.data.load --input data/demo
```

The eval command verifies `manifest.json`, all six file hashes, CSV headers and declared row counts before SQL. It then compares every typed field in all six domain tables, including inventory, in one read-only snapshot, ordered by primary key and streamed in batches of 1,000. Different values fail even if row counts match. Equivalent Decimal scales or timestamp offsets are accepted. Keep the bundle and database unchanged for the whole run: later tool calls use separate snapshots.

## Run

```bash
uv run python -m app.evals --bundle data/demo --provider reference
uv run python -m app.evals --bundle data/demo --provider mock --output mock.json
```

| Provider | What it measures |
| --- | --- |
| `reference` | The eval set itself: recorded tool calls must reproduce every oracle value (expected 42 / 42) |
| `mock` | The deterministic demo provider (baseline 17 / 42) |
| `openai` | The configured model; needs `LLM_PROVIDER=openai`, `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`, sends every question and tool result to OpenAI and costs money |

`--only M01 C01` runs selected cases; `--output` writes the full JSON report and refuses to overwrite a file. Runs are scored in memory and are not stored in `agent_runs`.

## Read the report

The terminal shows one line per case with failure notes, then a summary: `pass_rate`, `value_accuracy` (expected values cited, with failed runs counted as misses), `tool_selection_rate`, `refusal_rate`, `completed_rate`, results by kind, median and maximum latency, and total tokens for a real model. Each case in the JSON lists its checks, expected values, `tools_required`, called tools, the summary and the error code of a failed run.

Tool selection counts only cases with non-empty `tools_any` (38 in the full set). A failed run counts as a miss, while questions requiring no tool are excluded; an empty denominator yields `null`. On the recorded Stage 09 checks this gives reference 38 / 38 and mock 34 / 38 (0.8947), without changing the recorded question pass sets.

Undefined values are cited as `"null"`, matching JSON tool evidence: AOV with no paid orders, a change with an undefined AOV operand, and percentages or contribution shares with a zero denominator. Zero revenue, zero orders and refund-only negative revenue remain numeric when mathematically defined.

## Add a question

Add a case to `evals/cases.json` with an id such as `M09`, a `kind`, the `language`, reasonable `tools_any`, `expect` entries (metric, period, comparison period, category or region) and a `reference` call with the fields to cite. Run `uv run pytest tests/evals`: the reference run must pass the new case. If the mock now passes or fails differently, update `MOCK_BASELINE` in `tests/evals/test_agent_evals.py` and the results in [Evaluation](../EVALUATION.md).
