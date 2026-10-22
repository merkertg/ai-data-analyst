# AI Data Analyst

A Python learning project for an AI business analyst. It answers questions about the sales of IndustrialFlow, a fictional company that sells industrial equipment: pumps, compressors, valves and sensors. A manager asks in plain Russian or English, for example *"Why did revenue drop in September?"*, and the agent runs a short investigation. It calls deterministic analytics tools over PostgreSQL, obtains exact metrics and writes a report that separates facts, hypotheses and recommendations. The LLM chooses tools and explains their results; SQL and Python compute financial metrics. A local Streamlit interface shows the dashboard, Plotly charts, agent investigations and saved reports. The company, customers and sales data are fictional.

The project implements **all ten stages** of the course. PostgreSQL 17 holds six normalised sales tables with 28 integrity rules, money as `NUMERIC`/`Decimal` and a schema built only by Alembic migrations. A seeded generator creates 20,000 fictional orders for January–September 2026 with five recorded business anomalies; an atomic loader and quality checks keep the data consistent. A deterministic analytics core computes exact metrics, Moscow-time period comparisons and category or regional contributions; anomaly detection combines robust statistics, stockout rules and a seeded Isolation Forest. A FastAPI REST API serves all of this. The AI analyst answers natural-language questions through nine read-only tools in a bounded tool-calling loop and returns a report whose cited values and numbers are checked against the tool results; it runs with a deterministic demo provider by default or with the OpenAI Responses API when a key and model are configured. A Streamlit interface shows the dashboard, Plotly charts, agent investigations and saved reports over the HTTP API. Every `/api` route requires a bearer token stored only as a SHA-256 hash (`viewer` reads, `analyst` also saves reports and asks the agent), with per-token rate limits and a PostgreSQL statement timeout. 42 eval questions are scored against answers that a Pandas oracle computes independently from the CSV files: the reference run matches all 42 values, the demo provider passes 17, and a real model has not been measured yet. `docker compose up --build` starts the whole stand with demo data and an interface token; GitHub Actions checks the code with a 90% coverage gate, audits the locked dependencies, builds and smoke-tests the Docker stand and publishes the tested image to GHCR. Actual local results and the separately confirmed remote CI status are in [VERIFICATION.md](docs/VERIFICATION.md).

Current stabilization: **690 tests pass locally**, with **94.12% line and branch coverage**. Evals validate the entire six-table bundle; Compose supports reserved password characters; bootstrap keeps an analyst credential in a private file; dependency audits require a fresh valid report. See [verification](docs/VERIFICATION.md) for exact checks and limits.

macOS (Apple Silicon, locally) is verified. Earlier CI evidence is recorded per commit; the new delivery jobs and GHCR publication are not yet confirmed. On Windows use Docker Desktop: the stand runs in Linux containers ([Windows and PowerShell](docs/instructions/windows.md)).

**Начни с [демонстрации](docs/DEMO.md)** или с [быстрого запуска](docs/instructions/quickstart.md): `docker compose up --build`, затем интерфейс на <http://127.0.0.1:8502> и API на <http://127.0.0.1:8001/docs>. Демо-данные и токен интерфейса создаются автоматически; токены для API выдаёт команда `docker compose exec -T api python -m app.security issue --name 'Analyst' --role analyst`. Подробные руководства этапов на русском: [01](docs/STAGE_01.md) … [10](docs/STAGE_10.md); PDF — [на русском](docs/guide/ai-data-analyst-guide.pdf) и [на английском](docs/guide/ai-data-analyst-guide-en.pdf).

## Roadmap

| Stage | Work | Status |
| --- | --- | --- |
| 01 | Project setup: uv, FastAPI health endpoint, settings, tests, Ruff, mypy, CI | Implemented; verification results and commit-specific CI evidence are recorded separately |
| 02 | PostgreSQL, SQLAlchemy models, Alembic migrations | Implemented: six tables, 28 integrity rules, `/ready`, sample data, SQL examples, integration tests and a PostgreSQL service in CI |
| 03 | Demo data generation with injected anomalies and data quality checks | Implemented: seeded CSV bundle, manifest and evaluation ground truth, atomic loading into empty tables, read-only quality checks |
| 04 | Analytics core: revenue, orders, comparisons, category contributions | Implemented: exact SQL/Decimal metrics, Moscow date periods, monthly series, signed comparisons and a read-only JSON CLI |
| 05 | Anomaly detection: statistics and Isolation Forest | Implemented: retrospective robust statistics, IQR, stockout rules, seeded Isolation Forest, read-only CLI and separate scenario-coverage evaluation |
| 06 | REST API for metrics and analytics | Implemented: metrics, contributions, anomalies and saved report snapshots over FastAPI; validated query models, read-only snapshot sessions, migration `0002` for reports |
| 07 | AI agent with tool calling and structured outputs | Implemented: nine read-only tools with strict arguments, a bounded runtime, a structured report with verified evidence, mock and OpenAI providers, run history in migration `0003` |
| 08 | Streamlit interface, Plotly charts and reports | Implemented: HTTP-only Dashboard, AI analyst and Reports; exact labels, explicit saves, histories and JSON downloads |
| 09 | Unit, integration and agent evals, security checks | Implemented: API tokens with roles, rate limits, statement timeout, 55 security tests, 42 agent eval questions with an independent Pandas oracle, migration `0004` |
| 10 | Docker, CI/CD and publication | Implemented: one non-root image, a Compose stand with automatic demo data and interface token, coverage gate, dependency audit with dated exceptions, Docker smoke test and GHCR delivery of the tested image |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): the Docker stand in one command, requirements, installing uv, running PostgreSQL, the API and the interface on the host, local settings
- [Windows and PowerShell](docs/instructions/windows.md): Docker Desktop path and PowerShell equivalents of the Bash commands
- [Using the API](docs/instructions/usage.md): metrics, analytics, anomaly and report endpoints, parameters, saved reports, status codes
- [AI analyst](docs/instructions/agent.md): asking questions, mock and OpenAI providers, limits, report and evidence format, run history
- [Interface](docs/instructions/interface.md): starting Streamlit, settings, filters, charts, independent questions, histories and JSON downloads
- [Access tokens](docs/instructions/security.md): issuing, using, listing and revoking API tokens; roles, 401/403/429, rate-limit settings
- [Agent evals](docs/instructions/evals.md): preparing the database, running reference, mock or OpenAI evals, reading results, adding questions
- [Analytics](docs/instructions/analytics.md): exact metric definitions, period comparisons, category or regional contributions, JSON CLI
- [Anomaly detection](docs/instructions/anomalies.md): statistical and model candidates, evidence, thresholds, read-only CLI and offline evaluation limits
- [Demo data](docs/instructions/demo-data.md): generate, inspect, load and validate the reproducible dataset
- [Database](docs/instructions/database.md): Compose services, migrations, sample data, psql and SQL examples, schema changes
- [Testing and verification](docs/instructions/testing.md): Ruff, mypy, unit and integration tests, coverage gate, security tests, evals, dependency audit, Docker smoke test
- [CI and delivery to GHCR](docs/instructions/ci-and-delivery.md)
- [Project structure](docs/instructions/project-structure.md)

Stage learning guides in Russian:

- [Stage 01: project setup](docs/STAGE_01.md)
- [Stage 02: PostgreSQL, models and migrations](docs/STAGE_02.md)
- [Stage 03: reproducible demo data and quality checks](docs/STAGE_03.md)
- [Stage 04: deterministic analytics and comparisons](docs/STAGE_04.md)
- [Stage 05: anomaly detection and offline scenario evaluation](docs/STAGE_05.md)
- [Stage 06: REST API and saved reports](docs/STAGE_06.md)
- [Stage 07: AI agent, tool calling and verified reports](docs/STAGE_07.md)
- [Stage 08: Streamlit interface, charts and reports](docs/STAGE_08.md)
- [Stage 09: testing, agent evals and security](docs/STAGE_09.md)
- [Stage 10: Docker, CI/CD and publication](docs/STAGE_10.md)
- [Demo walkthrough](docs/DEMO.md)
- [CI/CD and Docker guide](docs/CI_CD.md)
- [Наглядное руководство PDF](docs/guide/ai-data-analyst-guide.pdf), [English PDF guide](docs/guide/ai-data-analyst-guide-en.pdf) и [его пересборка](docs/guide/README.md)
- [Полная проверка проекта](docs/VERIFICATION.md)
- [Обновление зависимостей и аудит](docs/DEPENDENCY_UPDATES.md)
- [Версии и публикация образа](docs/RELEASES.md)
- [Состояние проекта на 22 октября 2026 года](docs/PROJECT_STATUS_2026-10-22.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Security](docs/SECURITY.md): assets, threats, controls and known limits
- [Evaluation](docs/EVALUATION.md): eval method, results and interpretation
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)
