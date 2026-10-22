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

The eval command compares row counts with the CSV files and stops if they differ.

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

The terminal shows one line per case with failure notes, then a summary: `pass_rate`, `value_accuracy` (expected values cited), `tool_selection_rate`, `refusal_rate`, `completed_rate`, results by kind, median and maximum latency, and total tokens for a real model. Each case in the JSON lists its checks, expected values, called tools, the summary and the error code of a failed run.

## Add a question

Add a case to `evals/cases.json` with an id such as `M09`, a `kind`, the `language`, reasonable `tools_any`, `expect` entries (metric, period, comparison period, category or region) and a `reference` call with the fields to cite. Run `uv run pytest tests/evals`: the reference run must pass the new case. If the mock now passes or fails differently, update `MOCK_BASELINE` in `tests/evals/test_agent_evals.py` and the results in [Evaluation](../EVALUATION.md).
