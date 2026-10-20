# Project structure

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Where each part of the application, tests, and documentation lives.

```text
.github/workflows/
  ci.yml                 # Ruff, mypy and pytest on every push to main and pull request
app/
  __init__.py            # Package marker and the code version (__version__)
  config.py              # Settings from environment variables and .env
  main.py                # FastAPI application and GET /health
tests/
  test_health.py         # HTTP responses and the OpenAPI schema
  test_config.py         # Priority of defaults, .env and environment variables
  test_version.py        # app.__version__ matches pyproject.toml
scripts/
  build_guide.py         # Builds the Russian PDF guide (ReportLab, not a project dependency)
docs/
  instructions/          # Short task-oriented instructions (English)
  STAGE_01.md            # Detailed stage guide (Russian)
  CI_CD.md               # CI/CD guide (Russian)
  APPROACH.md            # Problem, solution, principles and architecture
  adr/                   # Architecture decision records
  DEVELOPMENT_LOG.md     # What was done at each stage and how it was checked
  VERIFICATION.md        # Recorded verification results and limits
  guide/                 # PDF guide, its verified data and rebuild instructions
.env.example             # Template for local settings; .env itself is not in Git
.gitignore               # .venv, tool caches, .env
.python-version          # Python version uv selects: 3.12
AGENTS.md                # Working rules for this repository
pyproject.toml           # Project metadata, dependencies, pytest/Ruff/mypy/uv settings
uv.lock                  # Exact versions and hashes of all 38 packages
```

Planned additions follow the course plan: `app/db/` and `migrations/` in Stage 02, `scripts/generate_data.py` and `data/demo/` in Stage 03, `app/analytics/` in Stages 04–05, `app/api/` in Stage 06, `app/agents/` and `app/llm/` in Stage 07, `frontend/` in Stage 08, and `tests/integration/`, `tests/evals/`, `tests/security/` in Stage 09.

## Configuration in pyproject.toml

| Section | Purpose |
| --- | --- |
| `[project]` | Name, version, Python requirement, runtime dependencies |
| `[dependency-groups] dev` | Test and check tools: httpx2, mypy, pytest, ruff |
| `[tool.uv]` | `exclude-newer`: only PyPI releases older than the cutoff date |
| `[tool.pytest.ini_options]` | `testpaths`, `pythonpath = ["."]`, `--strict-markers` |
| `[tool.ruff]`, `[tool.ruff.lint]` | Python 3.12 target, line length 88, rules `E F I UP B` |
| `[tool.mypy]` | Strict mode with the Pydantic plugin |

The project is an application, not a package: it was created with `uv init --app --no-package`, has no `[build-system]`, and is not installed into `.venv`. The reasons are recorded in [ADR 0001](../adr/0001-application-layout-and-tooling.md).
