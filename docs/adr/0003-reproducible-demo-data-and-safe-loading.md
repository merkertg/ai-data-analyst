# ADR 0003: Reproducible demo data and safe loading

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

Later analytics and agent evaluation need enough fictional sales data to show seasonal changes, discounts, refunds, stock availability and unusual order sizes. A random dataset without recorded evidence makes failures difficult to reproduce. Invalid rows would mix data quality errors with legitimate business anomalies. Loading demonstration data must not overwrite the development database or leave partially imported tables.

## Decision

- Generate a portable bundle through `python -m app.data.generate`. Defaults are 20,000 orders, 640 customers, 64 products and eight regions for January–September 2026, with seed 42.
- Use a local standard-library `random.Random` and explicit `Decimal` calculations. Do not add NumPy or Faker for generation. Serialize money as decimal text and retain the existing `NUMERIC` schema and Moscow reporting periods.
- Write six table CSV files, `manifest.json` with the schema version, seed, row counts and integrity hashes, and `ground_truth.json` with baseline and observed scenario evidence. Require a new or empty output directory; refuse overwrites. Keep generated bundles out of Git.
- Inject five valid business scenarios A01–A05. Treat coincident sales and stock changes as evidence to investigate, without claiming causal proof. Keep the answer key for evaluation only; the future runtime agent cannot use it as a data source.
- Validate the bundle before loading. Import through `python -m app.data.load`, using configured `DATABASE_URL`, only when all six domain tables are empty. Use one transaction and provide no reset option.
- Add read-only database checks through `python -m app.data.quality`: orders with at least one line, aggregate refunds not above the rounded discounted line amount, refunds only on paid orders, and refunds not before payment. Exit `0` on success and `1` on violations.
- Test integration behaviour only through `TEST_DATABASE_URL` with a database name ending in `_test`, preserving the Stage 02 isolation rule.

## Consequences

- Equal parameters produce equal artifact bytes and make scenario evaluation repeatable; a change to generation rules is a deliberate dataset contract change.
- Financial evidence comes from deterministic code, not the LLM. A quality pass proves specified integrity rules, not statistical normality or a business explanation.
- CSV files can be inspected independently of PostgreSQL. A manifest catches accidental changes; it is not authentication against an attacker who can rewrite both files and hashes.
- An interrupted or invalid import cannot leave a committed partial dataset. Existing sample or demo data is refused; choosing a separate empty database is an explicit operational step.
- A single-row database `CHECK` still cannot enforce aggregate refund limits. The quality command complements existing constraints without adding schema migrations or triggers in this stage.
- Analytics, automatic anomaly detection and the LLM agent remain separate later stages.
