# AI Data Analyst

AI analyst for **IndustrialFlow**, a fictional company that sells industrial
equipment: pumps, compressors, valves and sensors. A manager asks a question in
plain Russian or English, and the agent answers it by calling deterministic
analytics tools over PostgreSQL. The LLM picks the tools and explains the
result; every number comes from SQL or Python, never from the model.

> Learning project, built stage by stage. Explanations for each stage are in
> Russian (`docs/STAGE_*.md` and the PDF guide); code and technical docs are in
> English.

## Current status

| Stage | Topic | Status |
| --- | --- | --- |
| 01 | Project setup: uv, FastAPI, tests, Ruff, mypy, CI | Done |
| 02 | PostgreSQL schema, SQLAlchemy, Alembic | Next |
| 03 | Demo data generation and data quality checks | Planned |
| 04 | Analytics core: revenue, comparisons, contributions | Planned |
| 05 | Anomaly detection | Planned |
| 06 | REST API for metrics and analytics | Planned |
| 07 | AI agent with tool calling and structured outputs | Planned |
| 08 | Streamlit UI and reports | Planned |
| 09 | Tests, agent evals and security | Planned |
| 10 | Docker, CI/CD and publication | Planned |

Today the API exposes a single endpoint, `GET /health`.

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/) 0.12+. uv downloads Python 3.12
itself if it is missing.

```bash
uv sync --locked
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for the interactive API documentation, or:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Optional local settings: copy `.env.example` to `.env` and edit it.

## Checks

The same commands run in GitHub Actions on every push to `main` and every pull
request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run pytest
```

## Project layout

```text
app/            FastAPI application package
  __init__.py   package version
  config.py     settings from environment variables and .env
  main.py       FastAPI app and GET /health
tests/          pytest test suite
docs/           stage guides, development log, verification report, ADRs
scripts/        developer scripts (PDF guide builder)
.github/        CI workflow
```

## Documentation

- [Stage 01 guide (RU)](docs/STAGE_01.md) — detailed walkthrough of this stage
- [PDF guide (RU)](docs/guide/ai-data-analyst-guide.pdf) — visual summary
- [Approach](docs/APPROACH.md) — problem, solution and principles
- [Architecture decisions](docs/adr/)
- [Development log (RU)](docs/DEVELOPMENT_LOG.md) ·
  [Verification report (RU)](docs/VERIFICATION.md)
