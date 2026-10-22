# Quickstart

[← README](../../README.md) · [All documentation](../../README.md#documentation)

The fastest path is the Docker stand: one command starts the database, migrations, demo data, the API and the interface. The rest of this page runs the parts on the host for development. Detailed walkthroughs in Russian are in the stage guides [01](../STAGE_01.md) … [10](../STAGE_10.md); the [Stage 10 guide](../STAGE_10.md) explains the stand.

## Docker stand in one command

Needs only Docker with `docker compose` (Docker Desktop on macOS and Windows) and Git; no `.env`, uv or Python on the host.

```bash
git clone git@github.com:merkertg/ai-data-analyst.git
cd ai-data-analyst
docker compose up --build
```

| Service | Address or result |
| --- | --- |
| `ui` | Interface on <http://127.0.0.1:8502>, already signed in with an analyst token |
| `api` | <http://127.0.0.1:8001/docs>; `/ready` answers `{"status":"ready","revision":"0004"}` |
| `db` | PostgreSQL on `127.0.0.1:5436` (user `analyst`, database `industrialflow`) |
| `migrate` | Applies migrations, then exits |
| `bootstrap` | Loads the seed 42 demo data into an empty database and keeps the interface token, then exits |

The first build takes a few minutes; later starts take under a minute. Repeated starts keep data and the token. `docker compose down` stops the stand, `docker compose down --volumes` deletes its data. Busy ports: `API_PORT=8011 UI_PORT=8512 POSTGRES_PORT=5446 docker compose up`. A token for curl or another client:

```bash
docker compose exec -T api python -m app.security issue --name "me" --role analyst
```

Check the whole stand (Python 3 on the host, standard library only):

```bash
SMOKE_TOKEN="$(docker compose exec -T ui cat /run/ai-data-analyst/ui_token)" python3 scripts/smoke_stack.py
```

Without `.env` the stand uses a local demo database password; set `POSTGRES_PASSWORD` in `.env` for anything beyond a local demo. To use OpenAI instead of the demo provider, set `LLM_PROVIDER=openai`, `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env` and run `docker compose up --detach api`. See the [demo walkthrough](../DEMO.md) for what to show.

Compose passes the database host, port, name, user and raw password separately to `migrate`, `bootstrap` and `api`. Settings uses SQLAlchemy `URL.create(...)`, so passwords containing `@`, `/`, `#` or `%` need no manual URL encoding in `POSTGRES_PASSWORD`. Quote the value in `.env` when it contains special characters. The interface receives neither these database components nor the OpenAI key. The host's `DATABASE_URL` from `.env` is not forwarded into the containers.

Bootstrap keeps a valid analyst token. A viewer token is replaced with a new analyst token so the interface can also ask questions and save reports. Token writes use a unique `0600` temporary file and atomic replacement; failed writes leave no temporary credential copy. An existing valid analyst credential in a permissive file or behind a symlink is kept, while the file itself is replaced with a regular `0600` file without modifying the symlink's target.

## Requirements (host development)

- [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.12 or newer. The project and CI use uv 0.12.23.
- Python 3.12. You do not need to install it yourself: uv downloads it if it is missing.
- Docker with the `docker compose` command (Docker Desktop on macOS) for PostgreSQL 17.
- Git, to clone the repository.

Run all commands from the project root, the directory containing `pyproject.toml`.

## Supported platforms

| | macOS (Apple Silicon) | Linux |
| --- | --- | --- |
| Python on the host | `uv sync --locked`, Python 3.12 | same |
| PostgreSQL | Docker Desktop | Docker Engine or Desktop |
| Verification | Local checks recorded in VERIFICATION.md | Workflow targets `ubuntu-24.04`; see VERIFICATION.md for the confirmed remote result |
| Shell for the guides | zsh or Bash | Bash |

Windows is not checked in CI; use Docker Desktop or WSL 2 ([Windows and PowerShell](windows.md)).

## Install uv

The official installer of the pinned version:

```bash
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | sh
```

The installer puts `uv` into `~/.local/bin`. Open a new terminal tab and check the version:

```bash
uv --version
```

## Prepare the environment

```bash
uv sync --locked
cp .env.example .env
```

`uv sync --locked` creates `.venv` with the exact versions from `uv.lock` and fails if the lock file does not match `pyproject.toml`. `.env` holds local settings, including the database password and `DATABASE_URL`; it is ignored by Git. Always run project commands through `uv run`: the system `python3` may be a different version.

For host commands, keep `DATABASE_URL` aligned with the PostgreSQL credentials and published port. If its password contains reserved URL characters, percent-encode the password component; for example, `@` becomes `%40` and `/` becomes `%2F`. As an alternative, remove `DATABASE_URL` and set all connection components shown under [Local settings](#local-settings); their password is raw. See [Database](database.md#connection-settings) for details.

## Start PostgreSQL and apply migrations

```bash
docker compose up --detach --wait db
uv run alembic upgrade head
```

Choose a dataset before loading. On a new empty migrated database, generate and load the full demo dataset:

```bash
uv run python -m app.data.generate --output data/demo --seed 42 --orders 20000
uv run python -m app.data.load --input data/demo
uv run python -m app.data.quality
```

Generation requires a new or empty output directory. Loading requires all six domain tables to be empty and never overwrites existing data. The quality command is read-only; exit `0` means its rules pass. See [Demo data](demo-data.md) for scenarios, the manifest and evaluation ground truth.

For the small Stage 02 SQL exercise, use `uv run python -m app.db.sample` instead on a separate empty database. Do not load the sample before the full demo in the same database.

See [Database](database.md) for psql, SQL examples and schema changes.

## Calculate analytics

With a dataset loaded, calculate September and compare it with August:

```bash
uv run python -m app.analytics \
  --start 2026-09-01 --end 2026-10-01 \
  --compare-start 2026-08-01 --compare-end 2026-09-01 \
  --dimension category
```

The read-only CLI prints exact JSON metrics, monthly buckets, comparisons and contributions; monetary values are strings. Dates use a half-open Moscow interval. Use `--dimension region` for regional contributions; omit both comparison arguments for a summary and monthly series. No API server is required. See [Analytics](analytics.md) for definitions and manual sample answers.

## Detect anomaly candidates

Use the full generated history for monthly detection:

```bash
uv run python -m app.analytics.anomalies \
  --start 2026-01-01 --end 2026-10-01 \
  --output /tmp/anomalies.json
uv run python -m app.analytics.evaluate \
  --report /tmp/anomalies.json \
  --ground-truth data/demo/ground_truth.json
```

The first command reads current data without changing it and never reads the answer key. The second command is an offline coverage check for the five injected scenarios. Coverage is not precision or proof of causation. `--seed 42` is the model default; output paths must be new and are never overwritten. See [Anomaly detection](anomalies.md) for thresholds, full-month requirements and evaluation limits. No API server or LLM key is needed.

## Start the API

```bash
uv run uvicorn app.main:app --reload
```

Expected output:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`--reload` restarts the server when a `.py` file changes. Keep this terminal open and use a second tab for other commands:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

`/health` returns `{"status":"ok"}` — the process is up. `/ready` returns `{"status":"ready","revision":"0004"}` — the database is reachable and migrated; otherwise it answers `503`. Interactive documentation: <http://127.0.0.1:8000/docs>. Stop the server with `Ctrl+C`, and PostgreSQL with `docker compose stop`.

The `/api` routes need an API token (Stage 09). Issue one for yourself and keep it; it is shown only once (details in [Access tokens](security.md)):

```bash
uv run python -m app.security issue --name "local analyst" --role analyst
```

The same analytics are available over HTTP once data is loaded:

```bash
TOKEN='ida_…'
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/metrics/revenue?start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/analytics/anomalies?start=2026-01-01&end=2026-10-01"
```

See [Using the API](usage.md) for every endpoint, parameters and saved reports. Without HTTPS keep the server on `127.0.0.1`.

Ask the AI analyst. The default `mock` provider needs no model key; see [AI analyst](agent.md) to use OpenAI:

```bash
curl -X POST http://127.0.0.1:8000/api/agent/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question": "Why did revenue fall in September?"}'
```

If port 8000 is busy, choose another one: `--port 8001`.

## Local settings

Settings are read from environment variables, then from `.env`, then from defaults. Application settings live in `app/config.py`; the agent reads and caches `app/llm/config.py` settings only when a run starts. Restart the server after changing `.env` so cached settings are refreshed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `AI Data Analyst` | Service title in OpenAPI and on `/docs` |
| `DATABASE_URL` | not set | Explicit PostgreSQL address for the API and Alembic; takes priority over connection components; must start with `postgresql+psycopg://` |
| `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` | not set | Alternative when `DATABASE_URL` is absent: all four are required together; password is raw, stored as `SecretStr`, and escaped by `URL.create(...)` |
| `DATABASE_PORT` | `5432` | Port for the component-based configuration; host development uses the published port, normally `5436` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | see `.env.example` | Used by Docker Compose to create the `db` service |
| `POSTGRES_TEST_PORT` | `5437` | Host port of the `db-test` service |
| `LLM_PROVIDER` | `mock` | Demo planner; set `openai` for a real model |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | not set | Needed only by `openai`; choose a compatible model explicitly |

Agent time, step, tool and token limits are listed in [AI analyst](agent.md). Changing the provider does not change financial calculations: tools still use SQL and `Decimal`.

An explicit `DATABASE_URL` wins even if connection components are also supplied. If neither the URL nor connection components are configured, the API still starts: `/health` works and `/ready` answers `503`. A partially supplied component configuration is rejected; unset or remove `DATABASE_URL` rather than assigning an empty string to use the components.

## Open the interface (Stage 08)

Keep the API running and open a second terminal at the repository root:

```bash
uv run python -m streamlit run ui/main.py --server.address 127.0.0.1
```

Open <http://127.0.0.1:8501>. Dashboard has editable demonstration dates; Load dashboard requests the API. AI analyst submits independent questions, and Reports opens saved snapshots. `UI_API_URL` defaults to `http://127.0.0.1:8000`; the UI needs no database credentials or model key. See [Interface](interface.md) for charts, histories, downloads and errors.
