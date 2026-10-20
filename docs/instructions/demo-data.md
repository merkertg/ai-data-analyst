# Reproducible demo data

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Generate fictional IndustrialFlow data, load it into an empty migrated database, and check cross-table rules. The detailed Russian explanation is in [Stage 03](../STAGE_03.md); the design is in [ADR 0003](../adr/0003-reproducible-demo-data-and-safe-loading.md).

## Generate without a database

```bash
uv run python -m app.data.generate --output data/demo --seed 42 --orders 20000
```

The output directory must be new or empty. Use a different path for another run; the generator refuses to overwrite a bundle. The defaults are 640 customers, 64 products, eight regions and 20,000 orders for January–September 2026. The `--orders` range is 1,000–100,000; customer and product counts are fixed. Calendar periods use `Europe/Moscow`. Data is fictional. The standard-library generator uses its own seeded `random.Random` and `Decimal`, with no new runtime dependencies.

The bundle contains:

| File | Purpose |
| --- | --- |
| `customers.csv`, `products.csv`, `orders.csv` | Customers, product catalogue and orders |
| `order_items.csv`, `refunds.csv`, `inventory_snapshots.csv` | Order lines, processed refunds and daily stock snapshots |
| `manifest.json` | Schema version, seed, row counts and integrity hashes |
| `ground_truth.json` | Baseline and observed evidence for injected scenarios; evaluation only |

Identical parameters produce identical file bytes. Money is serialized as decimal text, never binary floats. Generated bundles are local artifacts; directories matching `data/demo*/` are ignored by Git. Keep custom output directories out of commits as well. To inspect CLI options, run `uv run python -m app.data.generate --help`.

## Load once into empty tables

```bash
docker compose up --detach --wait db
uv run alembic upgrade head
uv run python -m app.data.load --input data/demo
```

The loader uses `DATABASE_URL` from the normal project settings. It validates the six CSV files and the manifest; it never reads `ground_truth.json`. It checks the bundle and imports the six tables in one transaction, only when **all six domain tables are empty**. A failure rolls back the import; an existing dataset is refused. The loader has no reset or overwrite option. If the Stage 02 sample has already been loaded, use a separate empty migrated database for the generated dataset. Do not run the sample CLI before the demo loader in the same database.

## Check data quality

```bash
uv run python -m app.data.quality
```

The command only reads the configured database. Exit code `0` means its checks passed; `1` means one or more violations were found. It checks:

- every order must have at least one line;
- the sum of refunds for a line must not exceed `ROUND(quantity * unit_price * (1 - discount), 2)`;
- refunded orders must be paid;
- a refund must not precede its order's payment.

Database constraints cover row validity, foreign keys and uniqueness. These checks add rules that depend on several rows or tables. They do not repair data and do not classify unusual sales patterns as invalid.

## Scenarios A01–A05

| ID | Injected event |
| --- | --- |
| A01 | September paid pump line quantity becomes 40% of baseline, floored with a minimum of one |
| A02 | August paid valve lines in the South receive a 35% discount |
| A03 | July paid compressor lines receive additional refunds of 30% of the rounded line amount |
| A04 | Product 1 (a pump) has zero inventory snapshots on 10–19 September |
| A05 | One June paid sensor line has quantity 500 |

A03 is an extra 30% refund and can coexist with a baseline refund on the same line. These events are valid business data. `ground_truth.json` records what changed and the evidence needed to evaluate later analytics. The future agent must compute observations from the database, without reading the answer key. A01 and A04 happening together does not establish that a stockout caused the sales decline.

## Verify reproducibility and loading

Generate into two different new directories with the same parameters and compare their files. Unit tests check the generator and bundle validation; integration tests check loading, rollback, refusal of existing data and quality violations. Follow [Testing](testing.md), using only `TEST_DATABASE_URL` with a database name ending in `_test`. Actual local outcomes and remote CI status are recorded separately in [VERIFICATION.md](../VERIFICATION.md).
