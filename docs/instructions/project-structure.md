# Project structure

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Where each part of the application, tests, and documentation lives.

```text
.github/workflows/
  ci.yml                 # Ruff, mypy, migrations and pytest with a PostgreSQL service
app/
  __init__.py            # Package marker and the code version (__version__)
  config.py              # Settings from environment variables and .env; get_settings()
  main.py                # FastAPI application, GET /health and GET /ready
  db/
    base.py              # DeclarativeBase and the constraint naming convention
    models.py            # customers, products, orders, order_items, refunds, inventory_snapshots
    session.py           # Lazy engine (connection pool) and sessions
    readiness.py         # Schema version in the database vs the latest migration
    sample.py            # Small sample dataset with hand-computed answers (python -m app.db.sample)
  data/
    generate.py          # Seeded demo bundle CLI (python -m app.data.generate)
    load.py              # Validated atomic import into empty tables
    quality.py           # Read-only cross-table quality checks
migrations/
  env.py                 # Alembic: database URL from settings or tests, model metadata
  script.py.mako         # Template for new migration files
  versions/
    0001_initial_schema.py   # Six tables with keys, checks and indexes
data/demo/               # Generated CSV, manifest and ground truth; ignored by Git
sql/
  01_paid_order_totals.sql ... 04_double_counting.sql   # Hand-written queries, verified by tests
tests/
  test_health.py, test_config.py, test_version.py      # Stage 01 unit tests
  test_ready.py, test_session.py, test_models.py       # Stage 02 unit tests, no database
  test_demo_data.py, test_data_quality.py              # Stage 03 generation, bundle and quality unit tests
  integration/           # Real PostgreSQL from TEST_DATABASE_URL (*_test only)
    conftest.py          # Safety checks, migrated schema, rolled-back session per test
    test_migrations.py   # Upgrade, downgrade, alembic check, /ready
    test_constraints.py  # Integrity rules, delete rules, exact money, time zones
    test_queries.py      # The sql/ files on the sample dataset
    test_demo_data.py    # Loader, rollback, protected existing data and exact values
    test_data_quality.py # Cross-table violations on real PostgreSQL
scripts/
  build_guide.py         # Builds the PDF guide in Russian and English (ReportLab, not a project dependency)
  guide/                 # Guide modules: language pairs, layout, diagrams, project data, section texts
docs/
  instructions/          # Short task-oriented instructions (English)
  STAGE_01.md ... STAGE_03.md   # Detailed stage guides (Russian)
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

Planned additions follow the course plan: `app/analytics/` in Stages 04–05, `app/api/` in Stage 06, `app/agents/` and `app/llm/` in Stage 07, `frontend/` in Stage 08, and `tests/evals/`, `tests/security/` in Stage 09.

## Configuration in pyproject.toml

| Section | Purpose |
| --- | --- |
| `[project]` | Name, version, Python requirement, runtime dependencies (FastAPI, Uvicorn, pydantic-settings, SQLAlchemy, psycopg, Alembic) |
| `[dependency-groups] dev` | Test and check tools: httpx2, mypy, pytest, ruff |
| `[tool.uv]` | `exclude-newer`: only PyPI releases older than the cutoff date |
| `[tool.pytest.ini_options]` | `testpaths`, `pythonpath = ["."]`, `--strict-markers`, the `integration` marker |
| `[tool.ruff]`, `[tool.ruff.lint]` | Python 3.12 target, line length 88, rules `E F I UP B` |
| `[tool.mypy]` | Strict mode with the Pydantic plugin |

The project is an application, not a package: it was created with `uv init --app --no-package`, has no `[build-system]`, and is not installed into `.venv`. The reasons are recorded in [ADR 0001](../adr/0001-application-layout-and-tooling.md); the database decisions are in [ADR 0002](../adr/0002-postgresql-schema-and-migrations.md); generation and safe loading are in [ADR 0003](../adr/0003-reproducible-demo-data-and-safe-loading.md).
