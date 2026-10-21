# Analytics core

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Stage 04 provides deterministic SQL/Decimal metrics and a read-only JSON CLI. The detailed Russian walkthrough is [STAGE_04.md](../STAGE_04.md); the design is [ADR 0004](../adr/0004-deterministic-analytics-core.md). Metrics HTTP endpoints arrive in Stage 06.

Stage 05 builds [anomaly detection](anomalies.md) on this exact-money contract. Its separate CLI reads current data and produces statistical and Isolation Forest candidates; an offline evaluator alone reads the injected-scenario answer key. Candidates and group contributions provide evidence for investigation, not causal proof.

## Run

Start PostgreSQL, apply migrations and load either the demo or sample dataset as explained in the [quickstart](quickstart.md). The CLI uses `DATABASE_URL` from project settings; no API server is required.

```bash
uv run python -m app.analytics --start 2026-09-01 --end 2026-10-01
uv run python -m app.analytics \
  --start 2026-09-01 --end 2026-10-01 \
  --compare-start 2026-08-01 --compare-end 2026-09-01 \
  --dimension category
```

Use `--dimension region` for regional contributions. `category` is the default; only these two dimensions are accepted. Comparison boundaries are optional but must be supplied together. Run `uv run python -m app.analytics --help` for options. Invalid dates, empty or reversed intervals, unsupported dimensions and incomplete comparison arguments are rejected.

The JSON keys are `currency`, `timezone`, `summary`, `monthly`, `comparison`, `dimension` and `contributions`. Without a comparison period, `comparison` is `null` and `contributions` is an empty list; providing both comparison dates populates them. Decimal values are JSON strings, and unavailable AOV or percentage values are `null`. All queries in one CLI request use a read-only `REPEATABLE READ` transaction, so they see the same database snapshot.

## Periods and metrics

A period is `[start, end)` in `Europe/Moscow`: the start date at midnight is included, the end date at midnight is excluded. `2026-09-01` to `2026-10-01` means September. Monthly buckets include empty months, clip partial first/last months, and are limited to 120 calendar buckets.

| Field | Definition |
| --- | --- |
| `paid_sales` | Sum of rounded discounted lines of paid orders whose `paid_at` falls in the period |
| `refunds` | Sum of refunds whose `processed_at` falls in the period, on paid orders regardless of their payment month |
| `net_revenue` | `paid_sales - refunds` |
| `paid_orders` | Number of paid orders in the period; each order counts once |
| `average_order_value` | `paid_sales / paid_orders`, rounded to 2 decimal places; `null` without paid orders |

All amounts are RUB excluding VAT. Each line is `ROUND(quantity * unit_price * (1 - discount), 2)` before summing. Sales, order counts and refunds use independent aggregates to avoid multiplication by joins. Empty periods have zero amounts/counts and `null` AOV. Refund-only periods can have negative net revenue.

## Comparisons and contributions

`delta = current - previous`. Percentage change is `delta / abs(previous) * 100`, rounded to two decimal places with `ROUND_HALF_UP`; a zero previous value gives `null`. AOV comparisons are unavailable when either period has no paid orders. Totals are not adjusted for period length.

A category or region contribution is its signed net-revenue delta divided by the signed total delta, multiplied by 100. All groups from both periods are included, even when a group only has refunds. Results sort by delta ascending, then name. A zero total delta gives `null` percentages. Shares may exceed 100%, be negative, and differ from a 100% sum after rounding; this measures arithmetic contribution, not causation.

## Verify

```bash
uv run pytest tests/test_analytics_models.py tests/test_analytics_cli.py
uv run pytest tests/integration/test_analytics.py
```

Integration tests require `TEST_DATABASE_URL` ending in `_test`; see [Testing](testing.md). On a separate empty database loaded with `app.db.sample`, September has sales `310000.00`, refunds `1000.00`, net revenue `309000.00`, 2 paid orders and AOV `155000.00`; October has `18000.00`, `500.00`, `17500.00`, 1 and `18000.00`. These sample answers do not describe the 20,000-order generated bundle. Recorded test outcomes and remote CI evidence are in [VERIFICATION.md](../VERIFICATION.md).
