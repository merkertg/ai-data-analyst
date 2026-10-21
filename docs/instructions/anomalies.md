# Anomaly detection

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Stage 05 produces anomaly candidates from the current PostgreSQL data. It combines transparent statistical rules with a seeded scikit-learn Isolation Forest. Candidates are evidence to investigate; they do not establish a business cause. The detailed Russian walkthrough is [STAGE_05.md](../STAGE_05.md); the design is [ADR 0005](../adr/0005-anomaly-detection-and-offline-evaluation.md). HTTP analytics routes follow in Stage 06; no LLM or API key is needed.

## Detect

Start PostgreSQL, migrate and load the full demo as explained in the [quickstart](quickstart.md). The small Stage 02 sample is useful for SQL exercises but contains too little history for the monthly models.

```bash
uv run python -m app.analytics.anomalies \
  --start 2026-01-01 --end 2026-10-01 \
  --output /tmp/anomalies.json
```

The CLI uses `DATABASE_URL` from project settings and one read-only `REPEATABLE READ` transaction. It uses the same half-open Moscow reporting dates as [Analytics](analytics.md). It neither changes database rows nor reads `data/demo/ground_truth.json`. `--seed 42` is the default for the model. Without `--output`, JSON is printed to standard output. An output path must be new: existing files are not overwritten. Run `uv run python -m app.analytics.anomalies --help` for the complete argument contract.

Exact sales and refunds are aggregated independently in SQL, preserving `NUMERIC`/`Decimal` money. Ratios are calculated before conversion; only dimensionless model features become floating-point values. Unavailable rates and insufficient histories are skipped rather than silently treated as zero. Observation counts describe extracted inputs, not successfully scored rows. A clean report means no candidate met these rules within the supplied period; it does not prove that the business has no anomalies.

## Methods and defaults

| Method | Observation and reference | Candidate rule |
| --- | --- | --- |
| Robust monthly statistics | Paid quantity and refund/sales ratio by category; weighted discount rate by region/category; each point is compared with the other months of its own series | At least 6 other observations; `z = 0.6745 * (x - median) / MAD`; `abs(z) >= 6` |
| Zero-MAD fallback | The same leave-one-out reference when all or most reference values equal the median | Absolute difference is greater than `max(abs(median) * 0.25, floor)`; floor is `1` for quantity and `0.01` for rates |
| IQR | Paid line quantities within each category | At least 8 lines; quantity above `Q3 + 3 * (Q3 - Q1)` |
| Stockout rule | Daily inventory snapshots for each product | A maximal run of at least 3 consecutive zero-quantity days; a missing day breaks the run |
| Isolation Forest | Monthly region/category observations | At least 16 usable rows; a negative `decision_function` marks a candidate |

MAD is the median absolute deviation from the reference median. These are transparent demonstration defaults, not thresholds calibrated for real production data. Monthly statistics are retrospective: another month may occur after the month being scored. This is neither forecasting nor an unseen temporal holdout.

Anomaly features contain observed category/month combinations, including refund-only groups; completely empty groups are not zero-filled. A missing month therefore does not become a zero-volume statistical observation. The effective weighted discount rate is `(gross - rounded paid sales) / gross`; rounding a discounted line can erase a sub-kopeck nominal discount.

Isolation Forest uses four dimensionless features: quantity / series median quantity, paid sales / series median paid sales, weighted discount rate and refund/sales ratio. It uses 100 trees, `random_state=42` by default, `n_jobs=1` and `contamination="auto"`. Fitting and scoring use the supplied observations. The score measures how unusual an observation looks to this model; it is not a probability, a monetary loss or a causal explanation. Different methods can legitimately flag the same period.

Refunds are assigned by processing date, so a monthly refund/sales ratio can exceed 1 when refunds relate to earlier sales. A month without paid sales has no such ratio. Monthly statistical rules and Isolation Forest use only complete calendar months. Feature extraction retains clipped first/last buckets, but these are skipped by monthly detectors to avoid comparing partial-month volumes with full months. Line and inventory rules still use the requested interval.

## Report

The top-level JSON keys are `schema_version`, `period`, `seed`, `observations`, `configuration`, `finding_count` and `findings`. Observation counts separate `monthly`, `lines` and `stock`. Configuration records the history and threshold defaults. A finding contains `id`, `method`, `kind`, `period`, `entity`, `metric`, `observed`, `baseline` and `score`; decimal values remain strings. Robust scores are absolute z magnitudes, while a zero-MAD candidate has `score: null`. Isolation Forest findings store `-decision_function` as a positive score. Scores belong to their stated method and are not comparable probabilities.

## Evaluate injected scenarios offline

Only this separate command reads the answer key:

```bash
uv run python -m app.analytics.evaluate \
  --report /tmp/anomalies.json \
  --ground-truth data/demo/ground_truth.json
```

Use a report from the same bundle and time interval as the ground truth. Evaluation matches findings to the recorded scenario period and dimensions. Its JSON includes `total_scenarios`, `detected_scenarios`, `missed_scenarios`, `coverage_percent`, `matches` and `note`; `matches` maps each scenario ID to matching finding IDs. It measures coverage of the five injected positive scenarios A01–A05. The generator does not label every ordinary or naturally unusual observation, so this result cannot establish precision, a false-positive rate or independent model quality. Additional candidates are not automatically false positives. Repeatability on this demo does not establish generalisation to future or customer data.

Inspect each candidate's method, dimensions, period, observed value, reference, threshold and score. Then examine the underlying rows and consider competing hypotheses. Coexisting pump stockouts and lower pump quantities alone do not prove that one caused the other.

## Verify

Follow [Testing](testing.md) for unit and integration commands. Tests cover known positive and negative statistical cases, zero dispersion, short histories, stockout gaps, model reproducibility, independent SQL aggregates, date boundaries and separate ground-truth evaluation. Integration fixtures use only `TEST_DATABASE_URL` with an `_test` database. Actual local test and demo results, together with the separately checked remote CI status, are recorded in [VERIFICATION.md](../VERIFICATION.md).
