# ADR 0004: Deterministic analytics core

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The generated sales dataset needs a reusable, exact analytics contract before anomaly detection, the HTTP API and the LLM agent are added. Joining sales lines directly to multiple refunds can inflate sales. Counting joined lines can inflate order counts. UTC grouping assigns some early Moscow payments to the previous month. A multi-query CLI can also mix database states when concurrent writers commit between queries.

## Decision

- Implement the analytics core in `app/analytics/` using SQLAlchemy queries over PostgreSQL `NUMERIC` and Python `Decimal`. Add no runtime dependencies: defer Pandas and DuckDB until a concrete requirement justifies them.
- Represent periods as validated, non-empty half-open date intervals `[start, end)` whose boundaries are midnight in `Europe/Moscow`. Provide a calendar-month constructor. Generate zero-filled calendar buckets clipped to the requested period, with a maximum of 120 buckets.
- Include only paid orders. Recognise sales by `paid_at` and refunds by `processed_at`, including refunds of sales paid in an earlier period. Round each discounted line to two decimal places before summing. Aggregate sales, order counts and refunds independently.
- Define net revenue as paid sales minus processed refunds. Define AOV as paid sales divided by paid orders, rounded to two decimal places with `ROUND_HALF_UP`; use `None` when no orders were paid.
- Compare the supplied periods without length normalisation. Use `current - previous` and `(current - previous) / abs(previous) * 100`, rounded with `ROUND_HALF_UP`. Use `None` for a percentage with a zero baseline and for an AOV comparison when either AOV is unavailable.
- Allow only `category` and `region` as contribution dimensions. Union the groups from both periods, including refund-only groups. Divide each signed group net-revenue delta by the signed total delta; return `None` when total delta is zero. Sort by delta ascending, then group name.
- Expose `python -m app.analytics` as a JSON CLI. Require paired comparison boundaries; return the summary and monthly series for every request, and comparison/contributions only when a comparison period is supplied. Serialize decimal values as strings and unavailable values as JSON `null`.
- Run the CLI's queries in one read-only `REPEATABLE READ` transaction. Reusable functions accept a caller-owned session; callers choose their transaction boundary.
- Keep analytics endpoints for Stage 06 and anomaly detection for Stage 05. The core never calls an LLM or reads evaluation ground truth.

## Consequences

- Every amount is reproducible and traceable to deterministic SQL or Python. Separate aggregates avoid double counting and preserve paid order counts for multi-line orders.
- Empty months remain visible, while refund-only periods can have negative net revenue and an unavailable AOV.
- Negative baselines keep the direction of percentage change meaningful. A zero baseline is undefined, even if both periods equal zero.
- Contributions explain the arithmetic of change. A group may exceed 100% or have a negative share when another group offsets the decline; rounded shares need not sum to exactly 100%. This does not establish a business cause.
- Comparison periods can have different lengths or overlap. The output is an unadjusted total comparison, so users must choose periods suited to the question.
- A 120-bucket guard bounds monthly output. It is an input limit, not a query timeout or a security boundary.
- The snapshot makes one CLI response internally consistent. Consumers reusing the functions must arrange equivalent isolation if they require it.
- Integration verification uses only `TEST_DATABASE_URL` with an `_test` database. Actual local results and remote CI evidence remain separate in `docs/VERIFICATION.md`.
