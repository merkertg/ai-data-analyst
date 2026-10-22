# Evaluation

[← README](../README.md) · [All documentation](../README.md#documentation)

How the AI analyst is evaluated and what the results show. The detailed Russian explanation is in the [Stage 09 guide](STAGE_09.md); the commands are in [Agent evals](instructions/evals.md).

## Method

- **Questions.** [evals/cases.json](../evals/cases.json) holds 42 questions (27 Russian, 15 English): 8 metrics, 6 comparisons, 8 category or region contributions, 5 refunds, 4 products, 4 stock and anomaly questions, 3 questions without data, 3 refusals (delete data, run SQL, reveal the prompt and key) and 1 prompt injection.
- **Independent answers.** Expected values are not written in the file. `app/evals/oracle.py` computes them with Pandas from the six CSV files of the bundle, in integer kopecks with explicit half-up rounding, without PostgreSQL and without the analytics core. An AOV without paid orders, a change involving an undefined AOV, or a rate with a zero denominator is represented as `null`, exactly as in tool evidence; it is not zero or the Python string `"None"`.
- **Scoring.** A question passes when the run produces a verified report in the question's language, at least one reasonable tool succeeded, every expected value appears among the cited evidence of facts or hypotheses, refusal questions report no facts, and planted numbers do not appear in any text.
- **Providers.** `reference` makes the calls written in each case and cites the named fields: it checks the eval set and the tools against the oracle. `mock` is the deterministic demo provider. `openai` is the real model.
- **Dataset identity.** Before asking any question, the CLI verifies the export manifest, hashes, headers and row counts, then compares every typed field of all six domain tables, including `inventory_snapshots`, in one read-only database snapshot. Rows are matched by primary key and SQL results stream in batches of 1,000. Decimal scale and timestamp-offset formatting may differ when the values are equal; changed amounts or stock quantities fail even when counts match. This validation reuses the export loader's parsing, while expected financial values remain the oracle's independent calculation.
- **Isolation.** Runs use the production runtime, tools and evidence check, are scored in memory and are not stored. The identity check is at setup time; keep the bundle and database unchanged throughout an eval run because subsequent tool calls use their own snapshots.

`tool_selection_rate` measures only cases with a non-empty `tools_any`: 38 of the current 42 questions. A failed run is a miss; refusals and other questions requiring no tool do not add free successes. Each case records `tools_required`. If no selected case requires a tool, the rate is `null`. `value_accuracy` includes expected values from failed runs as misses.

## Stabilization rerun (22 October 2026)

Fresh runs inside the isolated Docker stand, after the six-table identity check:
[reference](../evals/results/2026-10-22-stabilization-reference.json),
[mock](../evals/results/2026-10-22-stabilization-mock.json).

| Provider | Passed | Value accuracy | Tool selection | Refusals | Median latency |
| --- | --- | --- | --- | --- | --- |
| reference | 42 / 42 | 1.0000 | 38 / 38 = 1.0000 | 3 / 3 | 5 ms |
| mock | 17 / 42 | 0.4737 | 34 / 38 = 0.8947 | 0 / 3 | 208 ms |
| openai | not measured | | | | |

No provider pass set changed. The different tool-selection rate reflects the
corrected denominator, rather than a change to the demo agent.

## Original Stage 09 results (22 October 2026)

Seed 42 bundle, 20,000 orders, "today" fixed to 1 October 2026. Full results: [reference](../evals/results/2026-10-22-reference.json), [mock](../evals/results/2026-10-22-mock.json).

| Provider | Passed | Value accuracy | Original tool selection | Refusals | Median latency |
| --- | --- | --- | --- | --- | --- |
| reference | 42 / 42 | 1.00 | 1.00 | 3 / 3 | 7 ms |
| mock | 17 / 42 | 0.47 | 0.90 | 0 / 3 | 214 ms |
| openai | not measured: no API key configured | | | | |

These files record the original Stage 09 run. Its tool-selection denominator included all 42 completed questions. Recounting those recorded checks with the current definition gives **reference 38 / 38 = 1.0**, **mock 34 / 38 = 0.8947**. The 42 / 42 and 17 / 42 pass sets are unchanged; this recount is not a new provider run.

| Kind | reference | mock |
| --- | --- | --- |
| metric | 8 / 8 | 2 / 8 |
| comparison | 6 / 6 | 3 / 6 |
| contribution | 8 / 8 | 6 / 8 |
| refunds | 5 / 5 | 3 / 5 |
| products | 4 / 4 | 0 / 4 |
| stock | 4 / 4 | 2 / 4 |
| no_data | 3 / 3 | 0 / 3 |
| refusal | 3 / 3 | 0 / 3 |
| injection | 1 / 1 | 1 / 1 |

## Interpretation

- The reference run shows that every question is answerable with the nine tools and that the SQL tools and the independent Pandas implementation agree on all 42 expected values, to the kopeck.
- The mock result is a floor, not a target: it parses only a month, a year and the language and always analyses one month. It never refuses, so all refusal and no-data questions fail.
- The evals found a real bug: the mock read the "dec" of "decline" as December. Month names are now matched as whole words.
- No language model has been evaluated. The same command with `--provider openai` measures one once a key is configured.

## Regression

`tests/evals/test_agent_evals.py` loads the seed 42 bundle into the `*_test` database in CI, requires the reference run to pass all cases and requires the mock to pass exactly the recorded 17 questions.

Pure tests cover undefined metrics and the metric denominators. `tests/integration/test_eval_dataset.py` checks real PostgreSQL equality and equal-count changes to each of the six tables, including stock; its database comes only from `TEST_DATABASE_URL` ending in `_test`.

## Limits

One dataset and one set of 42 questions; numeric agreement, not wording, reasoning quality or causality. Latency is from one Mac. Model results will vary between runs and model versions and must be recorded with the model name and date.
