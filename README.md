# AI Data Analyst

A Python learning project for an AI business analyst. It answers questions about the sales of IndustrialFlow, a fictional company that sells industrial equipment: pumps, compressors, valves and sensors. A manager asks in plain Russian or English, for example *"Why did revenue drop in September?"*, and the agent runs a short investigation. It calls deterministic analytics tools over PostgreSQL, computes exact metrics, builds charts and writes a report that separates facts, hypotheses and recommendations. The LLM chooses the tools and explains the results; every number comes from SQL or Python, never from the model. The company, customers and sales data are fictional.

The project is built in ten stages. **Stage 01 is implemented**: a FastAPI service with `GET /health` and a Pydantic response model, settings read from the environment and `.env` via pydantic-settings, seven pytest tests, Ruff linting and formatting, strict mypy, and a GitHub Actions workflow that runs the same checks on every push to `main` and every pull request. Dependencies are locked in `uv.lock`, and only PyPI releases at least 14 days old are accepted.

**Начни с [быстрого запуска](docs/instructions/quickstart.md)** или с [подробного руководства этапа 01](docs/STAGE_01.md). После запуска документация API: <http://127.0.0.1:8000/docs>.

## Roadmap

| Stage | Work | Status |
| --- | --- | --- |
| 01 | Project setup: uv, FastAPI health endpoint, settings, tests, Ruff, mypy, CI | Implemented; local checks pass, GitHub Actions run to be confirmed |
| 02 | PostgreSQL, SQLAlchemy models, Alembic migrations | Next |
| 03 | Demo data generation with injected anomalies and data quality checks | Planned |
| 04 | Analytics core: revenue, orders, comparisons, category contributions | Planned |
| 05 | Anomaly detection: statistics and Isolation Forest | Planned |
| 06 | REST API for metrics and analytics | Planned |
| 07 | AI agent with tool calling and structured outputs | Planned |
| 08 | Streamlit interface, Plotly charts and reports | Planned |
| 09 | Unit, integration and agent evals, security checks | Planned |
| 10 | Docker, CI/CD and publication | Planned |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): requirements, installing uv, starting the API, local settings
- [Using the API](docs/instructions/usage.md): `/health`, interactive docs, OpenAPI schema, status codes
- [Testing and verification](docs/instructions/testing.md): Ruff, mypy, pytest, lock and workflow checks
- [CI and delivery](docs/instructions/ci-and-delivery.md): what GitHub Actions runs and where to see the result
- [Project structure](docs/instructions/project-structure.md)

Stage learning guides in Russian:

- [Stage 01: project setup](docs/STAGE_01.md)
- [CI/CD guide](docs/CI_CD.md)
- [Наглядное руководство PDF](docs/guide/ai-data-analyst-guide.pdf) и [его пересборка](docs/guide/README.md)
- [Проверка проекта](docs/VERIFICATION.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)
