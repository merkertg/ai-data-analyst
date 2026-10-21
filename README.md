# AI Data Analyst

A Python learning project for an AI business analyst. It answers questions about the sales of IndustrialFlow, a fictional company that sells industrial equipment: pumps, compressors, valves and sensors. A manager asks in plain Russian or English, for example *"Why did revenue drop in September?"*, and the agent runs a short investigation. It calls deterministic analytics tools over PostgreSQL, computes exact metrics, builds charts and writes a report that separates facts, hypotheses and recommendations. The LLM chooses the tools and explains the results; every number comes from SQL or Python, never from the model. The company, customers and sales data are fictional.

The project is built in ten stages. **Stages 01–06 are implemented**: a FastAPI service with `GET /health` and `GET /ready`, settings from the environment and `.env`, and PostgreSQL 17 in Docker Compose. Six normalised tables enforce 28 named integrity rules, store money as `NUMERIC`/`Decimal` and are created only by Alembic migrations. Stage 03 adds a deterministic demonstration dataset: 20,000 orders, 640 customers, 64 products and eight regions from January to September 2026, five recorded business anomalies, an atomic loader and read-only data quality checks. Stage 04 adds a read-only analytics CLI and reusable SQL/Python functions for exact period metrics, zero-filled monthly series, comparisons, and category or regional contributions. Stage 05 adds statistical anomaly candidates, consecutive stockout rules and seeded Isolation Forest detection, with a separate offline evaluation of injected-scenario coverage. Detection reads the current database and never reads the ground truth. Stage 06 exposes all of this over a REST API: revenue and order metrics, category and regional contributions, anomaly candidates and saved report snapshots, with validated query models, read-only snapshot sessions, money as JSON strings and a 503 without internal details when the database is unavailable. A small sample dataset and four hand-written SQL queries remain available for learning joins, CTEs, window functions and double counting. Pytest, Ruff, strict mypy and a GitHub Actions workflow with a PostgreSQL service provide automated checks. Dependencies, including scikit-learn for Stage 05, are locked in `uv.lock`. Actual local results and the separately confirmed remote CI status are recorded in [VERIFICATION.md](docs/VERIFICATION.md).

Start with the [quickstart](docs/instructions/quickstart.md) or the detailed Russian stage guides [01](docs/STAGE_01.md), [02](docs/STAGE_02.md), [03](docs/STAGE_03.md), [04](docs/STAGE_04.md), [05](docs/STAGE_05.md) and [06](docs/STAGE_06.md). Visual PDF guides: [Russian](docs/guide/ai-data-analyst-guide.pdf) and [English](docs/guide/ai-data-analyst-guide-en.pdf). After starting the API, open <http://127.0.0.1:8000/docs>.

## Roadmap

| Stage | Work | Status |
| --- | --- | --- |
| 01 | Project setup: uv, FastAPI health endpoint, settings, tests, Ruff, mypy, CI | Implemented; local checks pass, GitHub Actions run to be confirmed |
| 02 | PostgreSQL, SQLAlchemy models, Alembic migrations | Implemented: six tables, 28 integrity rules, `/ready`, sample data, SQL examples, integration tests and a PostgreSQL service in CI |
| 03 | Demo data generation with injected anomalies and data quality checks | Implemented: seeded CSV bundle, manifest and evaluation ground truth, atomic loading into empty tables, read-only quality checks |
| 04 | Analytics core: revenue, orders, comparisons, category contributions | Implemented: exact SQL/Decimal metrics, Moscow date periods, monthly series, signed comparisons and a read-only JSON CLI |
| 05 | Anomaly detection: statistics and Isolation Forest | Implemented: retrospective robust statistics, IQR, stockout rules, seeded Isolation Forest, read-only CLI and separate scenario-coverage evaluation |
| 06 | REST API for metrics and analytics | Implemented: metrics, contributions, anomalies and saved report snapshots over FastAPI; validated query models, read-only snapshot sessions, migration `0002` for reports |
| 07 | AI agent with tool calling and structured outputs | Next |
| 08 | Streamlit interface, Plotly charts and reports | Planned |
| 09 | Unit, integration and agent evals, security checks | Planned |
| 10 | Docker, CI/CD and publication | Planned |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): requirements, installing uv, starting PostgreSQL and the API, local settings
- [Analytics](docs/instructions/analytics.md): exact metric definitions, period comparisons, category or regional contributions, JSON CLI
- [Anomaly detection](docs/instructions/anomalies.md): statistical and model candidates, evidence, thresholds, read-only CLI and offline evaluation limits
- [Demo data](docs/instructions/demo-data.md): generate, inspect, load and validate the reproducible dataset
- [Database](docs/instructions/database.md): Compose services, migrations, sample data, psql and SQL examples, schema changes
- [Using the API](docs/instructions/usage.md): metrics, analytics, anomaly and report endpoints, parameters, saved reports, status codes
- [Testing and verification](docs/instructions/testing.md): Ruff, mypy, unit and integration tests, migrations, lock and workflow checks
- [CI and delivery](docs/instructions/ci-and-delivery.md): what GitHub Actions runs and where to see the result
- [Project structure](docs/instructions/project-structure.md)

Stage learning guides in Russian:

- [Stage 01: project setup](docs/STAGE_01.md)
- [Stage 02: PostgreSQL, models and migrations](docs/STAGE_02.md)
- [Stage 03: reproducible demo data and quality checks](docs/STAGE_03.md)
- [Stage 04: deterministic analytics and comparisons](docs/STAGE_04.md)
- [Stage 05: anomaly detection and offline scenario evaluation](docs/STAGE_05.md)
- [Stage 06: REST API and saved reports](docs/STAGE_06.md)
- [CI/CD guide](docs/CI_CD.md)
- [Visual PDF guide](docs/guide/ai-data-analyst-guide.pdf), [English PDF guide](docs/guide/ai-data-analyst-guide-en.pdf) and [rebuild instructions](docs/guide/README.md)
- [Verification report](docs/VERIFICATION.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)
