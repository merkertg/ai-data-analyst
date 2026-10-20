# AI Data Analyst — Solution Approach

## Problem and product goal

IndustrialFlow, a fictional distributor of industrial equipment (pumps, compressors, valves, sensors), keeps orders, customers, products, refunds and inventory in a relational database. Managers ask questions such as *"Why did revenue drop in September? Which categories and regions contributed most? Are there anomalies?"* Answering them today means a manual round of SQL, a spreadsheet and a written summary.

The application answers such questions by running a short investigation: it selects data through a fixed set of analytics tools, performs exact calculations, builds charts and writes a structured report that separates facts, hypotheses and recommendations, each backed by tool results.

The project uses fictional IndustrialFlow data generated with a fixed seed.

## Current implementation: Stage 01

The application has a runnable HTTP foundation with locked dependencies, environment-based settings, automated tests and static checks. There is no database, data or analytics yet.

```text
HTTP client → Uvicorn → FastAPI
                         ├─ GET /health → HealthResponse {"status": "ok"}
                         └─ /docs, /redoc and /openapi.json → API documentation

Settings: environment variables → .env → defaults in app/config.py
```

`GET /health` reports that the process is up and answering HTTP. Its return annotation, `HealthResponse`, is both the documented schema and a runtime check: a response with a value other than `"ok"` is rejected by FastAPI with HTTP 500 instead of reaching the client. The application version lives in `app/__init__.py`, and a test keeps it equal to `version` in `pyproject.toml`.

`app/config.py` defines `Settings` on top of pydantic-settings. A value is taken from the process environment, then from `.env`, then from the default; unrelated keys in `.env` are ignored so later Docker and PostgreSQL variables can share the file.

`pyproject.toml` declares the Python requirement, dependencies and tool configuration. `uv.lock` records exact versions and hashes. `uv sync --locked` prepares `.venv` and fails when the lock file does not match the configuration. Only PyPI releases at least 14 days old are accepted (`[tool.uv] exclude-newer`).

## Stack and responsibility

| Component | Choice | Responsibility |
| --- | --- | --- |
| Language | Python 3.12 | API now; analytics and agent later |
| API | FastAPI | HTTP routing, validation, generated OpenAPI |
| ASGI server | Uvicorn | Local HTTP serving |
| Configuration | pydantic-settings | Environment and `.env` loading with validation |
| Dependency management | uv 0.12.23 | Isolated environment, locked dependencies, Python download |
| Testing | pytest, FastAPI TestClient on httpx2 | HTTP behaviour, configuration, version consistency |
| Code checks | Ruff, mypy (strict, Pydantic plugin) | Lint, formatting, import order, static types |
| CI | GitHub Actions | The same checks on every push to `main` and pull request |

Planned additions: PostgreSQL 17, SQLAlchemy 2 and Alembic (Stage 02); NumPy and Faker for demo data (Stage 03); Pandas and DuckDB for analytics (Stage 04); scikit-learn for anomaly detection (Stage 05); the OpenAI API for tool calling and structured outputs (Stage 07); Streamlit and Plotly (Stage 08); Docker Compose (Stages 02 and 10).

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

## Verification and CI

Seven pytest tests cover HTTP responses, the OpenAPI schema, the priority of settings sources and version consistency. Ruff checks style, import order and common bug patterns and formats both Python files and Python code blocks in Markdown. mypy runs in strict mode. GitHub Actions repeats these checks on `ubuntu-24.04` with SHA-pinned actions and read-only permissions. Recorded results are in [VERIFICATION.md](VERIFICATION.md); the workflow is explained in [CI_CD.md](CI_CD.md).

## Decisions

Architecture decisions are recorded as ADRs in [adr/](adr/):

- [ADR 0001: Application layout and tooling](adr/0001-application-layout-and-tooling.md) — `uv init --app --no-package`, `app/` at the root with pytest `pythonpath`, locked dependencies with a 14-day age policy, Ruff and strict mypy, `httpx2` for the test client.

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

Stage 02 adds PostgreSQL in Docker Compose, SQLAlchemy 2 models for customers, products, orders, order items, refunds and inventory snapshots, the first Alembic migration, a readiness check that includes the database, and integration tests for constraints.
