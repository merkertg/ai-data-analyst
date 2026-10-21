# AI Data Analyst — Solution Approach

## Problem and product goal

IndustrialFlow, a fictional distributor of industrial equipment (pumps, compressors, valves, sensors), keeps orders, customers, products, refunds and inventory in a relational database. Managers ask questions such as *"Why did revenue drop in September? Which categories and regions contributed most? Are there anomalies?"* Answering them today means a manual round of SQL, a spreadsheet and a written summary.

The application answers such questions by running a short investigation: it selects data through a fixed set of analytics tools, obtains exact calculations and writes a structured report that separates facts, hypotheses and recommendations, with references to tool results. The local Streamlit UI shows exact metric labels and interactive Plotly charts from API responses.

The project uses fictional IndustrialFlow data generated with a fixed seed.

## Current implementation: Stages 01–08

The application has a runnable HTTP foundation, a PostgreSQL schema created by versioned migrations, reproducible generated data, an atomic loader and read-only cross-table quality checks. A read-only analytics CLI and reusable functions calculate exact financial metrics, comparisons and contributions. Anomaly detection adds statistical rules, stockout runs and seeded Isolation Forest candidates, with a separate offline evaluation of injected-scenario coverage. A REST API exposes the same metrics, contributions and anomaly candidates and saves report snapshots. An AI analyst answers natural-language questions through nine read-only tools and returns a structured report. Its evidence references and recognised numeric literals are checked against tool results; this does not establish semantic or causal correctness.

```text
HTTP client → Uvicorn → FastAPI
                         ├─ GET /health → HealthResponse {"status": "ok"}
                         ├─ GET /ready  → connection + alembic_version == latest migration
                         ├─ GET /api/metrics/{revenue,orders}          ┐ query model (422),
                         ├─ GET /api/analytics/{categories,regions,     │ read-only snapshot
                         │                       anomalies}              │ session → services
                         ├─ POST /api/reports, GET /api/reports[/{id}]  ┘ → app.analytics
                         ├─ POST /api/agent/runs → AgentRuntime ⇄ provider (mock | OpenAI)
                         │     └─ ToolExecutor → 9 registered read-only tools → services
                         │        report → evidence check → agent_runs (history)
                         ├─ GET /api/agent/runs[/{id}] → stored investigations
                         └─ /docs, /redoc and /openapi.json → API documentation

Alembic migrations → PostgreSQL 17: customers, products, orders,
                     order_items, refunds, inventory_snapshots, reports,
                     agent_runs
Sample CLI (python -m app.db.sample) → small dataset with known answers
Generator (python -m app.data.generate) → CSV + manifest + evaluation ground truth
Loader (python -m app.data.load) → one transaction, empty domain tables only
Quality CLI (python -m app.data.quality) → read-only cross-table checks
Analytics CLI (python -m app.analytics) → read-only repeatable-read transaction
  ├─ PostgreSQL → independent sales, order-count and refund aggregates
  └─ Python Decimal → metrics, comparisons, monthly buckets and contributions
Detection CLI (python -m app.analytics.anomalies) → read-only repeatable-read snapshot
  ├─ SQL/Decimal features → robust statistics, IQR and consecutive stockout rules
  └─ dimensionless ratios → seeded scikit-learn Isolation Forest → candidates
Offline evaluator (python -m app.analytics.evaluate) → report + ground truth → coverage
sql/*.sql → hand-written queries, executed by integration tests

Settings: environment variables → .env → defaults in app/config.py
LLM settings: the same sources → app/llm/config.py, read only when the agent runs
```

`GET /health` reports that the process is up and answering HTTP; it never touches the database. Its return annotation, `HealthResponse`, is both the documented schema and a runtime check. `GET /ready` opens a connection, reads `alembic_version` and compares it with the latest migration shipped with the code. A missing `DATABASE_URL`, an unreachable server, an empty or outdated schema all return the same `503` without revealing the address. The application version lives in `app/__init__.py`, and a test keeps it equal to `version` in `pyproject.toml`.

`app/config.py` defines `Settings` on top of pydantic-settings and exposes it through a cached `get_settings()`. A value is taken from the process environment, then from `.env`, then from the default. `DATABASE_URL` must use the `postgresql+psycopg` driver and name a database; it is hidden from `repr` and validation errors because it contains a password.

`app/db/session.py` creates the engine lazily, checks pooled connections before reuse (`pool_pre_ping`) and limits connection attempts to three seconds. Sessions roll back on errors; code that writes data commits explicitly.

`pyproject.toml` declares the Python requirement, dependencies and tool configuration. `uv.lock` records exact versions and hashes. Only PyPI releases at least 14 days old are accepted (`[tool.uv] exclude-newer`).

## Stack and responsibility

| Component | Choice | Responsibility |
| --- | --- | --- |
| Language | Python 3.12 | API, database, deterministic analytics and the agent runtime |
| API | FastAPI | HTTP routing, validation, generated OpenAPI |
| ASGI server | Uvicorn | Local HTTP serving |
| Database | PostgreSQL 17 in Docker Compose | Persistent records, relational links, integrity rules |
| Database access | SQLAlchemy 2 with psycopg 3 | Typed models, connection pool, sessions and transactions |
| Anomaly model | scikit-learn Isolation Forest | Seeded candidates on dimensionless monthly features |
| LLM | OpenAI Responses API via the `openai` SDK 3.24.0; deterministic mock by default | Question interpretation, tool choice, explanation; never computes numbers |
| Schema changes | Alembic | Ordered creation, drift check and explicit rollback |
| Configuration | pydantic-settings | Environment and `.env` loading with validation |
| Dependency management | uv 0.12.23 | Isolated environment, locked dependencies, Python download |
| Testing | pytest, FastAPI TestClient on httpx2, real PostgreSQL | HTTP behaviour, settings, constraints, migrations, SQL results |
| Code checks | Ruff, mypy (strict, Pydantic plugin) | Lint, formatting, import order, static types |
| CI | GitHub Actions with a PostgreSQL service | The same checks on every push to `main` and pull request |

The Stage 03 generator uses only standard-library `random.Random`, `csv`, `hashlib` and exact `Decimal` arithmetic; it needs no NumPy or Faker. Stage 04 uses PostgreSQL aggregation and Python `Decimal` without new dependencies; Pandas and DuckDB are deferred until a concrete use case requires them ([ADR 0004](adr/0004-deterministic-analytics-core.md)). Stage 05 adds locked scikit-learn and its transitive dependencies, while exact monetary metrics remain SQL/Decimal. Stage 07 adds the official OpenAI SDK for tool calling and structured outputs. Stage 08 adds Streamlit 1.65.0 and Plotly 7.1.0. Pandas is now a transitive UI dependency, not a replacement for deterministic SQL/Decimal analytics. An application Docker image remains planned for Stage 10.

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

Two more tables hold results rather than business records and have no foreign keys to them: `reports` (Stage 06 snapshots) and `agent_runs` (Stage 07 investigations, with a CHECK that a completed run has a report and a failed run an error).

Deleting an order cascades to its lines; every other foreign key is `RESTRICT`, so customers with orders, sold products and refunded lines cannot be deleted. Constraint and index names follow a convention (`ck_`, `fk_`, `uq_`, `ix_` + table + columns). Rules spanning several tables — refunds not exceeding the line total, refunds only for paid orders — are verified by Stage 03 read-only data quality checks. Decisions are recorded in [ADR 0002](adr/0002-postgresql-schema-and-migrations.md).

## Key principles

1. **Numbers come from code, not from the model.** Revenue, averages, comparisons and anomaly scores are computed by deterministic SQL or Python. The LLM interprets the question, chooses tools and explains results.
2. **Restricted tools before free-form SQL.** The agent calls parameterised, pre-defined queries. Text-to-SQL, if added, will use a read-only role, table allow-lists and timeouts.
3. **Exact money arithmetic.** PostgreSQL `NUMERIC` and Python `Decimal`. Only dimensionless ratios are converted to floats for the anomaly model; monetary values are never recomputed by that model.
4. **Reproducibility.** Locked dependencies, seeded demo data and Isolation Forest, and a `ground_truth.json` of injected anomalies used only by the offline evaluator, never read by runtime detection or the agent.
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
- A period is a non-empty half-open date interval `[start, end)` interpreted at midnight in `Europe/Moscow`; timestamps are stored as `timestamptz`. `Period.month(year, month)` creates a calendar month. Monthly series include empty months and clip first and last buckets to the requested interval; at most 120 calendar buckets are accepted.
- Counts come from paid orders directly; sales and refunds are aggregated independently so multiple order lines or refunds cannot multiply money or order counts.
- Average order value is `None` when no orders were paid, including refund-only periods; sales, refunds, net revenue and order count are zero for an empty period.
- Comparisons use `current - previous`; percent change is `(current - previous) / abs(previous) * 100`, rounded to two decimal places with `ROUND_HALF_UP`. A zero previous value gives `None`, and an unavailable AOV gives `None` for its comparison. Period lengths are not normalised.
- Category or region contributions use signed group net-revenue deltas divided by the total delta. Zero total change gives `None`; percentages may exceed 100%, be negative, and differ from a 100% sum after rounding. Both periods contribute group names, including refund-only groups. Results sort by delta ascending, then name.
- JSON preserves monetary values as decimal strings and unavailable values as `null`. The CLI reads all requested results inside one read-only `REPEATABLE READ` transaction.

## Verification and CI

Unit tests cover HTTP responses, settings, schema structure, deterministic data generation and bundle handling, positive and negative anomaly cases, insufficient histories, stockout gaps, model reproducibility and offline coverage matching. Integration tests use a real PostgreSQL database whose name must end with `_test`: migrations, readiness, constraints, exact money and time round trips, SQL examples, data loading, cross-table quality rules, exact analytics and anomaly features against manual and generated fixtures. Tests use `TEST_DATABASE_URL` only and never the development `.env` address. Ruff checks style and formatting; mypy runs in strict mode over `app`, `ui`, `tests` and `migrations`. GitHub Actions repeats the configured checks on `ubuntu-24.04` with a PostgreSQL service, SHA-pinned actions and read-only permissions. Actual counts, results and limits belong in [VERIFICATION.md](VERIFICATION.md); local results do not establish a successful remote run. The workflow is explained in [CI_CD.md](CI_CD.md).

## Decisions

Architecture decisions are recorded as ADRs in [adr/](adr/):

- [ADR 0001: Application layout and tooling](adr/0001-application-layout-and-tooling.md) — `uv init --app --no-package`, `app/` at the root with pytest `pythonpath`, locked dependencies with a 14-day age policy, Ruff and strict mypy, `httpx2` for the test client.
- [ADR 0002: PostgreSQL schema, integrity rules and migrations](adr/0002-postgresql-schema-and-migrations.md) — six normalised tables, integrity enforced by PostgreSQL, `NUMERIC`/`Decimal` money, `timestamptz` with Moscow reporting months, Alembic as the only way to build the schema, `/ready`.

- [ADR 0003: Reproducible demo data and safe loading](adr/0003-reproducible-demo-data-and-safe-loading.md) — standard-library seeded generation, exact monetary serialization, manifest integrity, atomic loading and quality checks.
- [ADR 0004: Deterministic analytics core](adr/0004-deterministic-analytics-core.md) — explicit period semantics, independent SQL aggregates, exact comparisons, signed contributions and a snapshot-consistent CLI without Pandas or DuckDB.
- [ADR 0005: Anomaly detection and offline evaluation](adr/0005-anomaly-detection-and-offline-evaluation.md) — full-month retrospective rules, seeded Isolation Forest, exact feature extraction and separate positive-scenario coverage.
- [ADR 0006: REST API and saved reports](adr/0006-rest-api-and-saved-reports.md) — thin routers over shared services, validated query models, lazy read-only snapshot sessions, money as JSON strings, safe 503 mapping and immutable JSONB report snapshots.
- [ADR 0007: AI agent with tool calling and verified reports](adr/0007-ai-agent-tool-calling.md) — fixed read-only tools with strict arguments, a server-owned bounded loop, a structured report whose numbers are checked against tool results, mock and OpenAI providers, stored run history.

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

## Demonstration data and evaluation

The default bundle contains 640 customers, 64 products, 20,000 orders and daily inventory snapshots across eight regions for January–September 2026. The generator uses a local seeded `random.Random` instance and deterministic `Decimal` calculations. It writes the six table CSV files, `manifest.json` and `ground_truth.json` to a new or empty directory. Identical parameters produce identical file bytes. The manifest describes the schema version, seed, row counts and file hashes. Bundle validation protects the loader from incomplete or changed inputs; the loader refuses to overwrite existing business data and imports all tables in a single transaction. Loading needs only the six CSV files and the manifest; it never reads the evaluation answer key.

The five injected scenarios are valid business events, not deliberately invalid rows: reduced paid pump quantities in September (A01), 35% discounts on paid valve lines in the South in August (A02), additional refunds of 30% of rounded compressor line amounts in July (A03), zero snapshots for one pump on 10–19 September (A04), and one unusually large paid sensor line of 500 units in June (A05). A01 and A04 coexist in the dataset; this does not prove a causal stockout explanation for the sales drop.

`ground_truth.json` records baseline and observed deterministic evidence for evaluation. Runtime detection and the agent do not read it. Read-only data quality checks detect orders without lines, aggregate refunds above a rounded discounted line amount, refunds on unpaid orders and refunds processed before payment. A successful quality check establishes these rules only; it does not mean that sales behaviour is statistically ordinary.

Stage 05 extracts monthly category and region/category features, paid lines and stock snapshots directly from the current database. Robust statistics compare each complete calendar month with at least six other months of its series using a median and MAD. A zero-MAD fallback, an upper IQR fence for line quantities and a three-day consecutive-zero stock rule make their thresholds explicit. Isolation Forest fits and scores at least 16 usable complete-month rows using quantity and paid-sales ratios to series medians, weighted discount rate and refund/sales ratio. Its default seed is 42, with 100 trees, one worker and automatic contamination.

All findings are investigation candidates. The analysis is retrospective and is not forecasting or an unseen temporal holdout. Partial monthly buckets are retained as features but excluded from monthly detection. Only the separate offline evaluator reads the answer key and matches findings to A01–A05 by scope. This measures coverage of five injected positives, not precision, false-positive rate or independent generalisation. Additional candidates cannot automatically be labelled incorrect.

## REST API

`app/api/` contains thin FastAPI routers; `app/services/` arranges results of `app/analytics` into response models, so the API, the CLIs and the agent share the analytics implementation. Metric and analytics query parameters are Pydantic models with `extra="forbid"` and validators for half-open periods, the 120-month bound, paired comparison dates and the seed range; invalid requests receive 422. Each database-backed GET runs in a `REPEATABLE READ READ ONLY` session injected with `Depends`; sessions resolve the engine lazily on the first statement, because FastAPI resolves dependencies even for invalid parameters. Responses serialise `Decimal` money as JSON strings and undefined values as `null`. A missing or unreachable database maps to one 503 text without internal details.

`POST /api/reports` computes a comparison or anomaly result and stores it in the `reports` table (migration `0002`): UUID id, checked `kind`, request parameters and API-shaped result as JSONB, application version and creation time. Reports are immutable snapshots without foreign keys to sales rows. There is no authentication yet; the API is intended for `127.0.0.1` until the Stage 09 security work.

## AI agent

### LLM models

The provider is chosen by `LLM_PROVIDER`. The default `mock` provider needs no key or network: it runs a fixed four-step plan (coverage; comparison, categories, regions and refunds; anomalies and stock of the main category; report) over the real tools and marks its reports as demo mode, so the whole loop can be shown and tested offline. `openai` uses the Responses API with strict function tools, parallel tool calls and a strict JSON Schema text format; requests set `store=False` and carry the full history including any encrypted reasoning items. The application does not use a server-side conversation or `previous_response_id`; this is not a claim about all provider retention policies. There is no default model: `OPENAI_MODEL` must name a model compatible with all request options, including function calling, structured outputs and encrypted reasoning items. The base URL is fixed and retries are disabled. The adapter is tested with a fake SDK; a real OpenAI request and model quality have not been verified. Agent evaluations with known answers are planned for Stage 09.

### Agent tools

| Tool | Returns |
| --- | --- |
| `get_data_coverage` | Date ranges of sales, refunds and stock; exact category and region names |
| `get_revenue` | Period totals and monthly buckets |
| `compare_periods` | All metrics of two periods with exact changes |
| `get_sales_by_category`, `get_sales_by_region` | Net revenue change split by group, signed shares |
| `get_top_products` | Products by paid sales, optionally in one category |
| `get_refund_statistics` | Refund count, amount and refund-to-sales rate per category |
| `detect_anomalies` | Stage 05 candidates, rules before Isolation Forest, optional category |
| `get_inventory_history` | Zero-stock days per product; missing snapshots are not zeros |

Arguments are validated by strict Pydantic models before any SQL (unknown fields, coerced types, duplicate JSON keys, reversed or longer than 24-month periods are rejected and returned to the model as tool errors). Each call runs its own read-only `REPEATABLE READ` session; results above 16,000 characters are replaced by an error asking for a narrower request.

### Runtime and verification

`AgentRuntime` owns the loop: defaults are 8 model turns, 16 tool calls, 2 report corrections, a 120-second time budget and 120,000 transcript characters. The time budget is checked between operations, and model requests receive the smaller remaining timeout; an in-flight synchronous SQL/tool call is not interrupted at the deadline. The final `AnalysisReport` separates facts, hypotheses, recommendations and limitations. Each fact cites evidence (`call_id`, dotted field path, exact value). Every evidence reference must resolve to the exact scalar value from a successful tool call. Recognised numeric literals in facts and hypotheses must match their own evidence by magnitude; the summary, recommendations and limitations may use evidence from the whole report. ISO dates, calendar-context years, codes and cited names are excluded; bare four-digit amounts and numbers followed by units still require evidence. The checker does not prove metric identity, sign, date correctness or causation, and may not recognise number words or other notation. Problems are sent back as a correction. Completed runs and handled `LLMError` failures are stored in `agent_runs` with their partial trace when storage succeeds; configuration failures before the run and tool/database failures have no stored run. Runtime tools do not read the ground truth.

## Next steps

Stage 08 implements the local Streamlit interface described below. Stage 09 adds agent evaluations and security work; the live OpenAI path remains unverified without a key.

## Streamlit interface

`ui/main.py` runs only the selected page: Dashboard, AI analyst or Reports. `APIClient` uses standard-library urllib with a validated loopback origin, bounded responses and shared Pydantic response schemas. It ignores proxies, rejects redirects and never retries POST. UI settings have a 150-second default socket waiting timeout; timing out does not cancel work already started by the API. No UI code opens database connections or invokes the LLM.

Date forms are explicit, with editable demonstration presets and half-open Moscow periods. `DashboardSnapshot` stores the submitted query together with the three HTTP results, so unsubmitted widget edits cannot change the parameters of a save. Those GETs use separate database snapshots. Save recomputes through `POST /api/reports` and renders the returned immutable result. Plotly uses floats only for coordinates; exact money remains Decimal and string labels, hover customdata and JSON.

Each chat question is an independent investigation, not a continuation of previous messages. At most 20 entries stay in the current browser session; stored API history is paginated in sets of ten, including failed runs. A handled failure UUID can open its partial trace. Reports and investigations can be downloaded as JSON. `AppTest` checks actions and reruns with a fake API; a real-browser smoke check is recorded separately. See [ADR 0008](adr/0008-streamlit-interface.md).
