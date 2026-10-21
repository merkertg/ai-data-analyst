# Testing and verification

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Lint, formatting, type checks, migrations, unit and integration tests, and the lock file. The same commands run in [GitHub Actions](ci-and-delivery.md).

## Verify

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app tests migrations
docker compose --profile test up --detach --wait db-test
export TEST_DATABASE_URL='postgresql+psycopg://analyst:analyst_test@127.0.0.1:5437/industrialflow_test'
uv run --locked pytest -v
```

A successful run reports no Ruff or mypy issues and no failed tests. Exact test counts and actual local outcomes are recorded in [VERIFICATION.md](../VERIFICATION.md); the remote GitHub Actions result is confirmed separately. Without `TEST_DATABASE_URL`, local integration tests are skipped.

`ruff format` also checks Python code blocks inside Markdown files, so code examples in the documentation must be formatted too. Fix formatting with `uv run --locked ruff format .` and safe lint issues with `uv run --locked ruff check --fix .`.

## Unit and integration tests

| Group | Location | Needs a database |
| --- | --- | --- |
| Unit | `tests/*.py` | No |
| Integration | `tests/integration/` (marker `integration`) | Yes, from `TEST_DATABASE_URL` |

Integration tests drop and recreate the schema, so they only run against a database whose name ends with `_test`, and only from `TEST_DATABASE_URL` — never from `DATABASE_URL` or `.env`. Locally, without the variable they are skipped; on GitHub Actions (`CI=true`) a missing variable is a failure.

Fixtures: `migrated_engine` builds the schema once per run with `alembic downgrade base` → `upgrade head`; `db_session` runs each test inside a transaction that is rolled back afterwards, so tests never see each other's rows.

| File | Checks |
| --- | --- |
| `tests/test_health.py` | `/health`, `405` on `POST`, OpenAPI version and model |
| `tests/test_config.py` | Settings priority; `DATABASE_URL` driver and database validation; password hidden from errors and `repr` |
| `tests/test_ready.py` | `/ready` answers `503` without a database or with an unreachable one; `/health` does not need a database |
| `tests/test_session.py` | Lazy engine, `DatabaseNotConfigured`, disposing an unused pool |
| `tests/test_models.py` | Six domain tables plus `reports`, `NUMERIC(12, 2)` money, delete rules, named constraints, `OrderStatus` vs `CHECK` |
| `tests/test_version.py` | `app.__version__` matches `pyproject.toml` |
| `tests/integration/test_migrations.py` | Upgrade, downgrade round trip, rollback of `0002` alone, `alembic check`, `/ready` on a real database |
| `tests/integration/test_constraints.py` | 20 invalid rows rejected by the named constraint, cascade delete, exact `Decimal`, `timestamptz` |
| `tests/integration/test_queries.py` | The four files in `sql/` return hand-computed results on the sample data |
| `tests/test_demo_data.py`, `tests/test_data_quality.py` | Seeded generation, equal bundle bytes, money, scenarios, bundle validation and quality report behaviour |
| `tests/integration/test_demo_data.py`, `tests/integration/test_data_quality.py` | Empty-table loading, transaction rollback, existing-data refusal and cross-table quality violations |
| `tests/test_analytics_models.py`, `tests/test_analytics_cli.py` | Moscow periods, validation, exact/undefined percentage changes, dimensions, safe errors and JSON decimal serialization |
| `tests/integration/test_analytics.py` | Manual sample metrics, line-first rounding, independent sales/refund counts, Moscow boundaries, empty/partial months, comparisons, signed contributions and read-only behaviour |
| `tests/test_detection.py` | Positive and ordinary robust-statistic/IQR cases, zero MAD, short histories, full-month filtering, stockout gaps and Isolation Forest reproducibility |
| `tests/test_anomalies_cli.py`, `tests/test_anomaly_evaluation.py` | Input validation, safe errors, exact report JSON, exclusive report creation and separate positive-scenario coverage matching |
| `tests/integration/test_anomaly_features.py` | Exact SQL features, independent refund/sales aggregates, Moscow boundaries, partial buckets, line and stock scopes and read-only behaviour |
| `tests/test_api_validation.py` | Stage 06: invalid queries and report bodies get 422 without any SQL (a stand-in engine fails the test), non-UUID ids, 503 without `DATABASE_URL`, routes and error answers in OpenAPI |
| `tests/integration/test_api.py` | API answers equal hand-computed sample results and the analytics core, empty periods, report round trip and snapshot behaviour, listing, 404, `READ ONLY` `REPEATABLE READ` sessions |

Useful options:

```bash
uv run --locked pytest -m integration
uv run --locked pytest -m "not integration"
uv run --locked pytest -x
```

`-m` selects tests by marker; `-x` stops at the first failure. Stop the test database with `docker compose --profile test stop db-test`; its data lives in memory and disappears.

## Demo data

See [Demo data](demo-data.md) for the three CLI commands and their expected behaviour. Generation requires no database. The loader validates a complete bundle and writes only into empty domain tables in one transaction. The quality CLI is read-only; its exit code is `0` for passing checks and `1` for violations. Business scenarios A01–A05 are valid rows and must pass the quality checks.

For a manual check, generate two bundles in different new directories with the same seed and order count, then compare them with `diff -r`. Run destructive fixture and rollback tests only through the integration suite, with `TEST_DATABASE_URL` ending in `_test`.

## Analytics

See [Analytics](analytics.md) for CLI examples and metric definitions. The small `app.db.sample` fixture has hand-calculated September and October answers; it is different from the generated bundle. Tests cover zero baselines, negative revenue, refund-only periods, multiple refunds, boundary timestamps, clipped monthly buckets and contribution reconciliation. CLI tests also verify read-only `REPEATABLE READ` configuration and exact JSON values.

```bash
uv run pytest tests/test_analytics_models.py tests/test_analytics_cli.py
uv run pytest tests/integration/test_analytics.py
```

These test commands follow the same `_test` database safety rules above. They never use the development database for integration fixtures.

## Anomaly detection and offline evaluation

See [Anomaly detection](anomalies.md) for the detector and evaluator commands, defaults and limitations.

```bash
uv run pytest tests/test_detection.py tests/test_anomalies_cli.py \
  tests/test_anomaly_evaluation.py
uv run pytest tests/integration/test_anomaly_features.py
```

The same `_test` database safety rules apply. The detector never reads evaluation labels; the separate evaluator reads a report and `ground_truth.json` from the same bundle. Integration tests verify features against hand-computed data. Model tests use fixed numerical examples and seeds. Monthly rules and Isolation Forest skip partial calendar months; tests must preserve that distinction from clipped feature extraction.

For a full-bundle smoke check, use a dedicated empty `_test` database, explicitly point the CLIs at it, load the generated bundle, run quality checks, detect with seed 42 and evaluate separately. Repeat detection into a different new output path to compare JSON bytes; an existing output file is refused. Coverage of A01–A05 measures five injected positive scenarios. It is not precision, a false-positive rate or independent model quality, and additional candidates are not automatically incorrect. Record actual results in [VERIFICATION.md](../VERIFICATION.md); a local run does not confirm GitHub Actions.

## REST API

```bash
uv run --locked pytest tests/test_api_validation.py
uv run --locked pytest tests/integration/test_api.py
```

Unit tests replace `get_engine` with a function that fails the test, so a request rejected with 422 is proven never to reach SQL. Integration tests override the `read_session` and `write_session` dependencies with the rolled-back `_test` session and compare API answers with hand-computed sample results and the analytics core; one test opens the real read dependency and checks that PostgreSQL rejects a write. For a server smoke check, point `DATABASE_URL` at a dedicated `_test` database with the loaded bundle, apply migrations, run `uv run uvicorn app.main:app` and call the endpoints from [Using the API](usage.md).

## Migrations

```bash
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked alembic downgrade base
uv run --locked alembic upgrade head
```

`alembic check` prints `No new upgrade operations detected.` when models and migrations match. Run these against the test database by exporting `DATABASE_URL` with the same value as `TEST_DATABASE_URL`, as CI does.

## Lock file and dependency age

```bash
uv lock --check
```

The command fails if `uv.lock` does not match `pyproject.toml`; run `uv lock` and commit the updated file. The `[tool.uv] exclude-newer` date in `pyproject.toml` keeps `uv lock` from selecting PyPI releases published less than 14 days before it.

## Workflow file

```bash
uvx --from actionlint-py actionlint .github/workflows/ci.yml
```

No output and exit code `0` mean no issues.

## Clean-clone check

To reproduce what CI does on a fresh machine, clone the repository into a temporary directory and run the checks there:

```bash
git clone . /tmp/ai-data-analyst-check
cd /tmp/ai-data-analyst-check
uv sync --locked
uv run --locked pytest
```

Recorded results of every check are in the [verification report](../VERIFICATION.md).
