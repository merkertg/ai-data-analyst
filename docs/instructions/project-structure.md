# Project structure

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Where each part of the application, tests, and documentation lives.

```text
.github/workflows/
  ci.yml                 # Ruff, mypy, migrations and pytest with a PostgreSQL service
app/
  __init__.py            # Package marker and the code version (__version__)
  config.py              # Settings from environment variables and .env; get_settings()
  main.py                # FastAPI application, /health, /ready, error handlers and /api routers
  api/
    dependencies.py      # Lazy read-only snapshot and write sessions injected with Depends
    errors.py            # Unavailable database -> 503; agent errors -> their own safe status
    metrics.py           # GET /api/metrics/revenue and /orders
    analytics.py         # GET /api/analytics/categories, /regions and /anomalies
    reports.py           # POST /api/reports, GET /api/reports and /api/reports/{id}
    agents.py            # POST /api/agent/runs, GET /api/agent/runs and /api/agent/runs/{id}
  agents/
    tools.py             # Nine read-only tools, strict argument models, ToolExecutor
    runtime.py           # Bounded tool-calling loop: steps, calls, corrections, time, context
    schemas.py           # AnalysisReport: facts, hypotheses, recommendations, evidence; strict schema
    evidence.py          # Check exact evidence references and recognised numeric literals
    prompts.py           # System prompt, first message with today's date, correction message
    mock.py              # Deterministic demo provider over real tools (default, no key)
    provider.py          # Choose mock or OpenAI from settings
    contracts.py         # Tool calls, traces, turns, outcome and the provider protocol
  llm/
    config.py            # LLM_PROVIDER, OpenAI key and model, agent limits
    errors.py            # Safe agent errors with HTTP status, code and public message
    openai_provider.py   # Responses API: strict tools and report schema, store=False
  schemas/
    analytics.py         # Query models with period validation and response models (money as strings)
    reports.py           # Report requests (discriminated by kind) and responses
    agents.py            # Agent question, stored run, history list and failure answer
  services/
    analytics.py         # Build API responses from the analytics core; shared with the agent tools
    reports.py           # Create, read and list immutable report snapshots
    agents.py            # Run a question, store outcomes and handled agent failures, read history
  db/
    base.py              # DeclarativeBase and the constraint naming convention
    models.py            # Six sales tables, reports (Stage 06) and agent_runs (Stage 07)
    session.py           # Lazy engine (connection pool) and sessions
    readiness.py         # Schema version in the database vs the latest migration
    sample.py            # Small sample dataset with hand-computed answers (python -m app.db.sample)
  data/
    generate.py          # Seeded demo bundle CLI (python -m app.data.generate)
    load.py              # Validated atomic import into empty tables
    quality.py           # Read-only cross-table quality checks
  analytics/
    models.py            # Moscow date periods and exact metric/comparison result types
    service.py           # Independent SQL aggregates, monthly metrics, comparisons, contributions
    details.py           # Agent detail queries: coverage, top products, refunds, stock history
    __main__.py          # Read-only snapshot-consistent JSON CLI (python -m app.analytics)
    anomaly_models.py    # Exact feature and anomaly report types
    anomaly_features.py  # Independent SQL aggregates for monthly, line and stock features
    detection.py         # Robust statistics, IQR, consecutive stockouts and Isolation Forest
    anomalies.py         # Read-only detection CLI; never reads evaluation labels
    evaluate.py          # Separate offline matching against injected positive scenarios
migrations/
  env.py                 # Alembic: database URL from settings or tests, model metadata
  script.py.mako         # Template for new migration files
  versions/
    0001_initial_schema.py   # Six tables with keys, checks and indexes
    0002_add_saved_reports.py  # reports: UUID, kind, JSONB parameters and result, version, time
    0003_add_agent_runs.py     # agent_runs: question, status, report or error, JSONB trace
data/demo/               # Generated CSV, manifest and ground truth; ignored by Git
sql/
  01_paid_order_totals.sql ... 04_double_counting.sql   # Hand-written queries, verified by tests
tests/
  test_health.py, test_config.py, test_version.py      # Stage 01 unit tests
  test_ready.py, test_session.py, test_models.py       # Stage 02 unit tests, no database
  test_demo_data.py, test_data_quality.py              # Stage 03 generation, bundle and quality unit tests
  test_analytics_models.py, test_analytics_cli.py      # Stage 04 periods, comparisons, CLI validation/JSON
  test_detection.py, test_anomalies_cli.py             # Stage 05 rules, model, report CLI and safe output
  test_anomaly_evaluation.py                          # Separate positive-scenario coverage matching
  test_api_validation.py                              # Stage 06 parameter/body validation without SQL, 503, OpenAPI
  test_agent_tools.py, test_agent_evidence.py         # Stage 07 strict schemas, rejected calls, evidence rules
  test_agent_runtime.py, test_agent_mock.py           # Loop with a scripted model; demo planner
  test_openai_provider.py, test_agent_api.py          # Fake OpenAI SDK; agent routes without SQL
  integration/           # Real PostgreSQL from TEST_DATABASE_URL (*_test only)
    conftest.py          # Safety checks, migrated schema, rolled-back session per test
    test_migrations.py   # Upgrade, downgrade, alembic check, /ready
    test_constraints.py  # Integrity rules, delete rules, exact money, time zones
    test_queries.py      # The sql/ files on the sample dataset
    test_demo_data.py    # Loader, rollback, protected existing data and exact values
    test_data_quality.py # Cross-table violations on real PostgreSQL
    test_analytics.py    # Exact metrics, boundaries, monthly buckets, comparisons and contributions
    test_anomaly_features.py # Exact monthly/line/stock SQL features and read-only behaviour
    test_api.py          # API answers vs manual results and the core, report snapshots, READ ONLY sessions
    test_agent_tools.py  # Detail queries vs hand-checked answers; tools equal the REST API
    test_agent_api.py    # Full mock run, history, stored failed run, CHECK on agent_runs
scripts/
  build_guide.py         # Builds the PDF guide in Russian and English (ReportLab, not a project dependency)
  guide/                 # Guide modules: language pairs, layout, diagrams, project data, section texts
docs/
  instructions/          # Short task-oriented instructions (English)
  STAGE_01.md ... STAGE_07.md   # Detailed stage guides (Russian)
  CI_CD.md               # CI/CD guide (Russian)
  APPROACH.md            # Problem, solution, data model and architecture
  adr/                   # Architecture decision records
  DEVELOPMENT_LOG.md     # What was done at each stage and how it was checked
  VERIFICATION.md        # Recorded verification results and limits
  guide/                 # PDF guides (RU, EN), their verified data and rebuild instructions
alembic.ini              # Alembic settings; no database address inside
compose.yaml             # PostgreSQL 17: db (development) and db-test (profile test)
.env.example             # Template for local settings; .env itself is not in Git
.gitignore               # .venv, tool caches, .env
.python-version          # Python version uv selects: 3.12
AGENTS.md                # Working rules for this repository
pyproject.toml           # Project metadata, dependencies, pytest/Ruff/mypy/uv settings
uv.lock                  # Exact versions and hashes of all resolved packages
```

The REST API (Stage 06) lives in `app/api/`, the AI analyst (Stage 07) in `app/agents/` and `app/llm/`. The Streamlit interface (Stage 08) lives in `ui/`; it calls the API over HTTP. Planned additions follow the course plan: `tests/evals/` and `tests/security/` in Stage 09.

## Configuration in pyproject.toml

| Section | Purpose |
| --- | --- |
| `[project]` | Name, version, Python requirement, runtime dependencies (FastAPI, Uvicorn, pydantic-settings, SQLAlchemy, psycopg, Alembic, scikit-learn, openai) |
| `[dependency-groups] dev` | Test and check tools: httpx2, mypy, pytest, ruff |
| `[tool.uv]` | `exclude-newer`: only PyPI releases older than the cutoff date |
| `[tool.pytest.ini_options]` | `testpaths`, `pythonpath = ["."]`, `--strict-markers`, the `integration` marker |
| `[tool.ruff]`, `[tool.ruff.lint]` | Python 3.12 target, line length 88, rules `E F I UP B` |
| `[tool.mypy]` | Strict mode with the Pydantic plugin |

The project is an application, not a package: it was created with `uv init --app --no-package`, has no `[build-system]`, and is not installed into `.venv`. The reasons are recorded in [ADR 0001](../adr/0001-application-layout-and-tooling.md); the database decisions are in [ADR 0002](../adr/0002-postgresql-schema-and-migrations.md); generation and safe loading are in [ADR 0003](../adr/0003-reproducible-demo-data-and-safe-loading.md); the deterministic analytics contract is in [ADR 0004](../adr/0004-deterministic-analytics-core.md); anomaly detection and offline coverage limits are in [ADR 0005](../adr/0005-anomaly-detection-and-offline-evaluation.md); the REST API and saved reports are in [ADR 0006](../adr/0006-rest-api-and-saved-reports.md); the AI agent is in [ADR 0007](../adr/0007-ai-agent-tool-calling.md).

## Streamlit interface (Stage 08)

`ui/main.py` renders Dashboard, AI analyst and Reports. `ui/client.py` validates bounded HTTP responses against the shared API schemas; `ui/config.py` reads local UI connection settings. `ui/charts.py` turns results into Plotly charts with exact money labels; `ui/models.py` keeps submitted dashboard and chat snapshots across reruns. `.streamlit/config.toml` configures a loopback server and the theme. Start from the repository root with `uv run python -m streamlit run ui/main.py --server.address 127.0.0.1`; using Python as a module keeps the repository on the import path. See [Interface](interface.md).
