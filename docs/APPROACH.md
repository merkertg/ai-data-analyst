# AI Data Analyst — Solution Approach

## Problem and product goal

IndustrialFlow, a fictional distributor of industrial equipment (pumps, compressors, valves, sensors), keeps orders, customers, products, refunds and inventory in a relational database. Managers ask questions such as *"Why did revenue drop in September? Which categories and regions contributed most? Are there anomalies?"* Answering them today means a manual round of SQL, a spreadsheet and a written summary.

The application answers such questions by running a short investigation: it selects data through a fixed set of analytics tools, performs exact calculations, builds charts and writes a structured report that separates facts, hypotheses and recommendations, each backed by tool results.

The project uses fictional IndustrialFlow data generated with a fixed seed.

## Current implementation: Stages 01–02

The application has a runnable HTTP foundation, a PostgreSQL schema created by versioned migrations, and automated checks against a real database. There is no generated dataset and no analytics yet.

```text
HTTP client → Uvicorn → FastAPI
                         ├─ GET /health → HealthResponse {"status": "ok"}
                         ├─ GET /ready  → connection + alembic_version == latest migration
                         └─ /docs, /redoc and /openapi.json → API documentation

Alembic migrations → PostgreSQL 17: customers, products, orders,
                     order_items, refunds, inventory_snapshots
Sample CLI (python -m app.db.sample) → small dataset with known answers
sql/*.sql → hand-written queries, executed by integration tests

Settings: environment variables → .env → defaults in app/config.py
```

`GET /health` reports that the process is up and answering HTTP; it never touches the database. Its return annotation, `HealthResponse`, is both the documented schema and a runtime check. `GET /ready` opens a connection, reads `alembic_version` and compares it with the latest migration shipped with the code. A missing `DATABASE_URL`, an unreachable server, an empty or outdated schema all return the same `503` without revealing the address. The application version lives in `app/__init__.py`, and a test keeps it equal to `version` in `pyproject.toml`.

`app/config.py` defines `Settings` on top of pydantic-settings and exposes it through a cached `get_settings()`. A value is taken from the process environment, then from `.env`, then from the default. `DATABASE_URL` must use the `postgresql+psycopg` driver and name a database; it is hidden from `repr` and validation errors because it contains a password.

`app/db/session.py` creates the engine lazily, checks pooled connections before reuse (`pool_pre_ping`) and limits connection attempts to three seconds. Sessions roll back on errors; code that writes data commits explicitly.

`pyproject.toml` declares the Python requirement, dependencies and tool configuration. `uv.lock` records exact versions and hashes. Only PyPI releases at least 14 days old are accepted (`[tool.uv] exclude-newer`).

## Stack and responsibility

| Component | Choice | Responsibility |
| --- | --- | --- |
| Language | Python 3.12 | API and database code now; analytics and agent later |
| API | FastAPI | HTTP routing, validation, generated OpenAPI |
| ASGI server | Uvicorn | Local HTTP serving |
| Database | PostgreSQL 17 in Docker Compose | Persistent records, relational links, integrity rules |
| Database access | SQLAlchemy 2 with psycopg 3 | Typed models, connection pool, sessions and transactions |
| Schema changes | Alembic | Ordered creation, drift check and explicit rollback |
| Configuration | pydantic-settings | Environment and `.env` loading with validation |
| Dependency management | uv 0.12.23 | Isolated environment, locked dependencies, Python download |
| Testing | pytest, FastAPI TestClient on httpx2, real PostgreSQL | HTTP behaviour, settings, constraints, migrations, SQL results |
| Code checks | Ruff, mypy (strict, Pydantic plugin) | Lint, formatting, import order, static types |
| CI | GitHub Actions with a PostgreSQL service | The same checks on every push to `main` and pull request |

Planned additions: NumPy and Faker for demo data (Stage 03); Pandas and DuckDB for analytics (Stage 04); scikit-learn for anomaly detection (Stage 05); the OpenAI API for tool calling and structured outputs (Stage 07); Streamlit and Plotly (Stage 08); an application Docker image (Stage 10).

## Data model

```text
customers 1 ──< orders 1 ──< order_items >── 1 products 1 ──< inventory_snapshots
                                  1
                                  └──< refunds
```

| Table | Key columns | Integrity rules |
| --- | --- | --- |
| `customers` | `name`, `region`, `industry` | Non-blank text |
| `products` | `sku` (unique), `name`, `category`, `cost NUMERIC(12,2)` | `cost >= 0` |
| `orders` | `customer_id`, `status`, `ordered_at`, `paid_at` (`timestamptz`) | Status in `pending/paid/cancelled`; paid ⇔ `paid_at` set; `paid_at >= ordered_at` |
| `order_items` | `order_id`, `product_id`, `quantity`, `unit_price NUMERIC(12,2)`, `discount NUMERIC(5,4)` | `quantity > 0`, `unit_price >= 0`, `0 <= discount < 1`, one line per product per order |
| `refunds` | `order_item_id`, `amount NUMERIC(12,2)`, `processed_at` | `amount > 0` |
| `inventory_snapshots` | `product_id`, `snapshot_date`, `quantity` | `quantity >= 0`, one snapshot per product per day |

Deleting an order cascades to its lines; every other foreign key is `RESTRICT`, so customers with orders, sold products and refunded lines cannot be deleted. Constraint and index names follow a convention (`ck_`, `fk_`, `uq_`, `ix_` + table + columns). Rules spanning several tables — refunds not exceeding the line total, refunds only for paid orders — are left to Stage 03 data quality checks. Decisions are recorded in [ADR 0002](adr/0002-postgresql-schema-and-migrations.md).

## Key principles

1. **Numbers come from code, not from the model.** Revenue, averages, comparisons and anomaly scores are computed by deterministic SQL or Python. The LLM interprets the question, chooses tools and explains results.
2. **Restricted tools before free-form SQL.** The agent calls parameterised, pre-defined queries. Text-to-SQL, if added, will use a read-only role, table allow-lists and timeouts.
3. **Exact money arithmetic.** PostgreSQL `NUMERIC` and Python `Decimal`, never `float`.
4. **Reproducibility.** Locked dependencies, seeded demo data, and a `ground_truth.json` of injected anomalies used only for evaluation, never read by the agent.
5. **Modular monolith.** One FastAPI service with clear internal layers; no microservices.

## Metric definitions

Fixed before any data exists, so that every later stage uses the same rules:

- All amounts are in RUB, excluding VAT.
- Sales are recognised on the payment date; only paid orders count.
- Processed refunds reduce revenue in the period they are processed.
- Cancelled and unpaid orders are excluded.
- Net revenue = paid sales − processed refunds.
- Average order value = paid sales / paid orders, before refunds.
- A line amount is `ROUND(quantity * unit_price * (1 - discount), 2)`; an order total is the sum of its lines.
- Reporting periods are calendar months in `Europe/Moscow` time; timestamps are stored as `timestamptz`.

## Verification and CI

26 unit tests cover HTTP responses, the OpenAPI schema, settings and `DATABASE_URL` validation, readiness without a database, the lazy engine and the model structure. 34 integration tests run on a real PostgreSQL database whose name must end with `_test`: migrations up and down, `alembic check`, `/ready`, 20 invalid rows rejected by the expected named constraint, delete rules, exact `Decimal` round trips, time zones, and the four SQL files on the sample dataset. Ruff checks style and formats both Python files and Python code blocks in Markdown; mypy runs in strict mode over `app`, `tests` and `migrations`. GitHub Actions repeats all of this on `ubuntu-24.04` with a digest-pinned PostgreSQL service, SHA-pinned actions and read-only permissions. Recorded results are in [VERIFICATION.md](VERIFICATION.md); the workflow is explained in [CI_CD.md](CI_CD.md).

## Decisions

Architecture decisions are recorded as ADRs in [adr/](adr/):

- [ADR 0001: Application layout and tooling](adr/0001-application-layout-and-tooling.md) — `uv init --app --no-package`, `app/` at the root with pytest `pythonpath`, locked dependencies with a 14-day age policy, Ruff and strict mypy, `httpx2` for the test client.
- [ADR 0002: PostgreSQL schema, integrity rules and migrations](adr/0002-postgresql-schema-and-migrations.md) — six normalised tables, integrity enforced by PostgreSQL, `NUMERIC`/`Decimal` money, `timestamptz` with Moscow reporting months, Alembic as the only way to build the schema, `/ready`.

## Architecture

The target architecture after all ten stages:

```text
Streamlit interface: chat, dashboard, charts, reports
             ↓ HTTP / JSON
FastAPI: validation, access control, request handling
             ↓
AI analyst agent: LLM, analysis plan, tool calling
     ├─ SQL tools → repositories → PostgreSQL
     ├─ Python tools → Pandas, anomaly detection
     └─ report builder → facts, conclusions, charts, sources, limits
```

The interface talks only to the API. The agent can call only registered tools; each tool runs a predefined parameterised query or a Python calculation and returns structured results that the report cites.

## Next steps

Stage 03 generates the demonstration dataset: about 20,000 orders from January to September 2026, 500–1,000 customers, 50–100 products and 8 sales regions, with injected scenarios A01–A05 recorded in a `ground_truth.json` that the agent never reads. A seeded generator makes the dataset reproducible, and data quality checks cover the rules that a single-row `CHECK` cannot express.
