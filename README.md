# AI Data Analyst

A Python learning project for an AI business analyst. It answers questions about the sales of IndustrialFlow, a fictional company that sells industrial equipment: pumps, compressors, valves and sensors. A manager asks in plain Russian or English, for example *"Why did revenue drop in September?"*, and the agent runs a short investigation. It calls deterministic analytics tools over PostgreSQL, obtains exact metrics and writes a report that separates facts, hypotheses and recommendations. The LLM chooses tools and explains their results; SQL and Python compute financial metrics. A local Streamlit interface shows the dashboard, Plotly charts, agent investigations and saved reports. The company, customers and sales data are fictional.

The project is built in ten stages. **Stages 01–09 are implemented**: a FastAPI service with `GET /health` and `GET /ready`, settings from the environment and `.env`, and PostgreSQL 17 in Docker Compose. Six normalised tables enforce 28 named integrity rules, store money as `NUMERIC`/`Decimal` and are created only by Alembic migrations. Stage 03 adds a deterministic demonstration dataset: 20,000 orders, 640 customers, 64 products and eight regions from January to September 2026, five recorded business anomalies, an atomic loader and read-only data quality checks. Stage 04 adds a read-only analytics CLI and reusable SQL/Python functions for exact period metrics, zero-filled monthly series, comparisons, and category or regional contributions. Stage 05 adds statistical anomaly candidates, consecutive stockout rules and seeded Isolation Forest detection, with a separate offline evaluation of injected-scenario coverage. Detection reads the current database and never reads the ground truth. Stage 06 exposes all of this over a REST API: revenue and order metrics, category and regional contributions, anomaly candidates and saved report snapshots, with validated query models, read-only snapshot sessions, money as JSON strings and a 503 without internal details when the database is unavailable. Stage 07 adds the AI analyst: a tool-calling loop with server limits over nine read-only analytics tools, a structured report with facts, hypotheses, recommendations and limitations, and an evidence check for exact tool references and recognised numeric literals. The check has explicit exclusions and does not prove that an explanation is correct; see [its limits](docs/STAGE_07.md#8-проверка-доказательств). It runs with a deterministic demo provider by default or with the OpenAI Responses API when a key and compatible model are configured. Completed runs and handled agent failures are stored with their tool traces when the database is available; configuration failures before a run starts are not stored. Stage 08 adds a local HTTP-only Streamlit client: editable dashboard filters, exact metric labels, Plotly charts, independent agent questions with evidence and traces, paginated histories, explicit report saving and JSON downloads. Stage 09 adds access control and measurement: every `/api` route needs a bearer token (stored only as a SHA-256 hash; `viewer` reads, `analyst` also saves reports and asks the agent), per-token rate limits, a PostgreSQL statement timeout, security tests that attack the API and the agent, and 42 eval questions whose answers a Pandas oracle computes independently from the CSV files. The reference run matches all 42 values; the demo provider passes 17; a real model has not been measured yet. A small sample dataset and four hand-written SQL queries remain available for learning joins, CTEs, window functions and double counting. Pytest, Ruff, strict mypy and a GitHub Actions workflow with a PostgreSQL service provide automated checks. Dependencies, including scikit-learn for Stage 05 and the OpenAI SDK for Stage 07, are locked in `uv.lock`. Actual local results and the separately recorded remote CI status are in [VERIFICATION.md](docs/VERIFICATION.md).

Start with the [quickstart](docs/instructions/quickstart.md) or the detailed Russian stage guides [01](docs/STAGE_01.md), [02](docs/STAGE_02.md), [03](docs/STAGE_03.md), [04](docs/STAGE_04.md), [05](docs/STAGE_05.md), [06](docs/STAGE_06.md), [07](docs/STAGE_07.md), [08](docs/STAGE_08.md) and [09](docs/STAGE_09.md). Visual PDF guides: [Russian](docs/guide/ai-data-analyst-guide.pdf) and [English](docs/guide/ai-data-analyst-guide-en.pdf). After starting the API, open <http://127.0.0.1:8000/docs>.

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
| 10 | Docker, CI/CD and publication | Next |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): requirements, installing uv, starting PostgreSQL and the API, local settings
- [Analytics](docs/instructions/analytics.md): exact metric definitions, period comparisons, category or regional contributions, JSON CLI
- [Anomaly detection](docs/instructions/anomalies.md): statistical and model candidates, evidence, thresholds, read-only CLI and offline evaluation limits
- [Demo data](docs/instructions/demo-data.md): generate, inspect, load and validate the reproducible dataset
- [Database](docs/instructions/database.md): Compose services, migrations, sample data, psql and SQL examples, schema changes
- [Using the API](docs/instructions/usage.md): metrics, analytics, anomaly and report endpoints, parameters, saved reports, status codes
- [Interface](docs/instructions/interface.md): starting Streamlit, filters, charts, independent questions, histories and JSON downloads
- [AI analyst](docs/instructions/agent.md): asking questions, mock and OpenAI providers, limits, report and evidence format, run history
- [Access tokens](docs/instructions/security.md): issuing, using, listing and revoking API tokens; roles, 401/403/429, rate-limit settings
- [Agent evals](docs/instructions/evals.md): preparing the database, running reference, mock or OpenAI evals, reading results, adding questions
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
- [Stage 07: AI agent, tool calling and verified reports](docs/STAGE_07.md)
- [Stage 08: Streamlit interface, charts and reports](docs/STAGE_08.md)
- [Stage 09: testing, agent evals and security](docs/STAGE_09.md)
- [CI/CD guide](docs/CI_CD.md)
- [Visual PDF guide](docs/guide/ai-data-analyst-guide.pdf), [English PDF guide](docs/guide/ai-data-analyst-guide-en.pdf) and [rebuild instructions](docs/guide/README.md)
- [Verification report](docs/VERIFICATION.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Security](docs/SECURITY.md): assets, threats, controls and known limits
- [Evaluation](docs/EVALUATION.md): eval method, results and interpretation
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)

## Run the interface

Start the API using the [quickstart](docs/instructions/quickstart.md), then run a second terminal from the repository root:

```bash
uv run python -m streamlit run ui/main.py --server.address 127.0.0.1
```

Open <http://127.0.0.1:8501>. The default API URL is `http://127.0.0.1:8000`; configure `UI_API_URL`, `UI_API_TOKEN` (an API token from `python -m app.security issue`) and `UI_REQUEST_TIMEOUT_SECONDS` in the environment or `.env`. Questions are separate investigations rather than a multi-turn conversation. A report save recomputes current data, then displays the returned immutable snapshot.
