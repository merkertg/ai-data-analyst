# Quickstart

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Install uv, prepare the environment, start the API and optionally override settings with a local `.env` file. A detailed walkthrough in Russian is in the [Stage 01 guide](../STAGE_01.md).

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.12 or newer. The project and CI use uv 0.12.23.
- Python 3.12. You do not need to install it yourself: uv downloads it if it is missing.
- Git, to clone the repository.

Run all commands from the project root, the directory containing `pyproject.toml`.

## Supported platforms

| | macOS (Apple Silicon) | Linux |
| --- | --- | --- |
| Python on the host | `uv sync --locked`, Python 3.12 | same |
| Verified by | Local run: tests, Ruff, mypy, Uvicorn, curl | GitHub Actions on `ubuntu-24.04` |
| Shell for the guides | zsh or Bash | Bash |

Windows is not checked yet. Docker Compose arrives in Stage 02 together with PostgreSQL.

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
uv run --locked python --version
```

`uv sync --locked` creates `.venv` with the exact versions from `uv.lock` and fails if the lock file does not match `pyproject.toml`. The second command must print `Python 3.12.x`. Always run project commands through `uv run`: the system `python3` may be a different version.

## Start the API

```bash
uv run --locked uvicorn app.main:app --reload
```

Expected output:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`--reload` restarts the server when a `.py` file changes. Keep this terminal open and use a second tab for other commands. Check the service:

```bash
curl http://127.0.0.1:8000/health
```

The response is `{"status":"ok"}`. Interactive documentation: <http://127.0.0.1:8000/docs>. Stop the server with `Ctrl+C`.

If port 8000 is busy, choose another one: `--port 8001`.

## Local settings

Settings are read from environment variables, then from `.env`, then from defaults in `app/config.py`. To keep local values, copy the template:

```bash
cp .env.example .env
```

`.env` is ignored by Git. Settings are read at startup, so restart the server after changing `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `AI Data Analyst` | Service title in OpenAPI and on `/docs` |

A one-off override without `.env`:

```bash
APP_NAME="IndustrialFlow Analytics" uv run --locked uvicorn app.main:app
```
