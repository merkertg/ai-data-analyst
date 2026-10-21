# ADR 0005: Anomaly detection and offline evaluation

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

The exact Stage 04 metrics and Stage 03 demo allow reproducible anomaly investigations. Five injected scenarios describe known positive events, but they are not a complete labelling of normal behaviour. Detection must find evidence in the current database without accessing the answer key. Financial metrics must keep their exact arithmetic even when a numerical model requires floats.

## Decision

- Add reusable feature extraction and detectors in `app/analytics/`, plus `python -m app.analytics.anomalies` and a separate `python -m app.analytics.evaluate` CLI. Keep HTTP routes for Stage 06 and LLM calls for Stage 07.
- Read the requested half-open Moscow period using a read-only `REPEATABLE READ` snapshot. Aggregate sales, refunds and line quantities independently, retaining `NUMERIC`/`Decimal` money. Convert only dimensionless ratios to floats for scikit-learn.
- Apply leave-one-out robust monthly statistics to category paid quantities and refund/sales ratios, and region/category weighted discount rates. Require at least six other observations. Flag `abs(0.6745 * (x - median) / MAD) >= 6`. When MAD is zero, require the absolute difference to exceed `max(abs(median) * 0.25, floor)`, with floor 1 for quantity or 0.01 for rates.
- Use only complete calendar months for monthly statistical rules and Isolation Forest. Keep clipped feature buckets visible, but skip them for monthly detection rather than comparing incomplete volumes with full months. Line and inventory rules retain the requested date range.
- Detect unusually large paid lines per category with the upper `Q3 + 3 * IQR` fence after at least eight samples. Detect maximal consecutive zero-inventory runs lasting at least three days; missing snapshots break a run.
- Add locked scikit-learn while preserving the dependency-age cutoff. Fit Isolation Forest on at least 16 usable monthly region/category observations using four dimensionless features: quantity and paid sales relative to the respective series medians, weighted discount rate and refund/sales ratio. Use 100 trees, seed 42 by default, `n_jobs=1` and `contamination="auto"`; a negative decision function produces a candidate.
- Skip unavailable rates and insufficient histories rather than inventing zero denominators. Report extracted observation counts, which do not imply that every row was scored. Do not fabricate empty category/month groups as zero observations. Report evidence with the method, period, dimensions, observed value and reference or score.
- Treat every finding as a candidate for investigation. Defaults are explicit demonstration settings. The analysis is retrospective; fitting and scoring the supplied history is neither a forecast nor an independent holdout evaluation.
- Keep `ground_truth.json` outside detection. The offline evaluator matches candidates to the five injected positive scenarios and reports scenario coverage. It does not claim precision, a false-positive rate or generalisation because the answer key contains no complete negative labelling.
- Print JSON to standard output by default. When an output path is supplied, create a new file exclusively and refuse to overwrite an existing report.

## Consequences

- SQL and Python continue to compute every financial amount exactly; model input conversion does not redefine financial metrics.
- Statistical rules explain their references and thresholds. Isolation Forest can add multivariate candidates but does not assign causal meaning or a calibrated probability to its score.
- Short histories can produce no statistical or model result. Partial months are excluded from monthly detection; refund timing can still affect ratios and needs interpretation.
- Multiple methods can report overlapping candidates. A stockout and a sales reduction in the same period are insufficient to establish causation.
- Locked dependencies, fixed inputs, seed and one worker make demo runs reproducible within the recorded environment. Results remain dataset- and version-specific.
- Unit tests verify positive and negative cases and determinism; integration tests verify exact feature extraction on the dedicated `_test` database. Local outcomes and remote GitHub Actions evidence remain separate in `docs/VERIFICATION.md`.

## Reference

The official [IsolationForest API](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) defines the estimator parameters and decision-function convention. The repository pins the actual library version in `uv.lock`; demonstration thresholds and feature choices are project decisions.
