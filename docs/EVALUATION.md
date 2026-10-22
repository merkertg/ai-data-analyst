# Evaluation

[← README](../README.md) · [All documentation](../README.md#documentation)

How the AI analyst is evaluated and what the results show. The detailed Russian explanation is in the [Stage 09 guide](STAGE_09.md); the commands are in [Agent evals](instructions/evals.md).

## Method

- **Questions.** [evals/cases.json](../evals/cases.json) holds 42 questions (27 Russian, 15 English): 8 metrics, 6 comparisons, 8 category or region contributions, 5 refunds, 4 products, 4 stock and anomaly questions, 3 questions without data, 3 refusals (delete data, run SQL, reveal the prompt and key) and 1 prompt injection.
- **Independent answers.** Expected values are not written in the file. `app/evals/oracle.py` computes them with Pandas from the six CSV files of the bundle, in integer kopecks with explicit half-up rounding, without PostgreSQL and without the analytics core.
- **Scoring.** A question passes when the run produces a verified report in the question's language, at least one reasonable tool succeeded, every expected value appears among the cited evidence of facts or hypotheses, refusal questions report no facts, and planted numbers do not appear in any text.
- **Providers.** `reference` makes the calls written in each case and cites the named fields: it checks the eval set and the tools against the oracle. `mock` is the deterministic demo provider. `openai` is the real model.
- **Isolation.** The database must hold the same bundle (row counts are compared first). Runs use the production runtime, tools and evidence check, are scored in memory and are not stored.

## Results (22 October 2026)

Seed 42 bundle, 20,000 orders, "today" fixed to 1 October 2026. Full results: [reference](../evals/results/2026-10-22-reference.json), [mock](../evals/results/2026-10-22-mock.json).

| Provider | Passed | Value accuracy | Tool selection | Refusals | Median latency |
| --- | --- | --- | --- | --- | --- |
| reference | 42 / 42 | 1.00 | 1.00 | 3 / 3 | 7 ms |
| mock | 17 / 42 | 0.47 | 0.90 | 0 / 3 | 214 ms |
| openai | not measured: no API key configured | | | | |

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

## Limits

One dataset and one set of 42 questions; numeric agreement, not wording, reasoning quality or causality. Latency is from one Mac. Model results will vary between runs and model versions and must be recorded with the model name and date.
