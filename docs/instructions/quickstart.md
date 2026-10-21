# Quickstart

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Install uv, start PostgreSQL, apply migrations, start the API and check that it is ready. Detailed walkthroughs in Russian are in the [Stage 01](../STAGE_01.md), [Stage 02](../STAGE_02.md), [Stage 03](../STAGE_03.md) and [Stage 04](../STAGE_04.md) guides.

## Requirements

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

Windows is not checked yet.

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

`/health` returns `{"status":"ok"}` — the process is up. `/ready` returns `{"status":"ready","revision":"0001"}` — the database is reachable and migrated; otherwise it answers `503`. Interactive documentation: <http://127.0.0.1:8000/docs>. Stop the server with `Ctrl+C`, and PostgreSQL with `docker compose stop`.

If port 8000 is busy, choose another one: `--port 8001`.

## Local settings

Settings are read from environment variables, then from `.env`, then from defaults in `app/config.py`. Settings are read at startup, so restart the server after changing `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `AI Data Analyst` | Service title in OpenAPI and on `/docs` |
| `DATABASE_URL` | not set | PostgreSQL address for the API and Alembic; must start with `postgresql+psycopg://` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | see `.env.example` | Used by Docker Compose to create the `db` service |
| `POSTGRES_TEST_PORT` | `5437` | Host port of the `db-test` service |

Without `DATABASE_URL` the API still starts: `/health` works and `/ready` answers `503`.
