# Testing and verification

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Lint, formatting, type checks, tests and the lock file. The same commands run in [GitHub Actions](ci-and-delivery.md).

## Verify

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app tests
uv run --locked pytest -v
```

Expected results after Stage 01:

| Command | Result |
| --- | --- |
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `... files already formatted` |
| `mypy app tests` | `Success: no issues found in 6 source files` |
| `pytest -v` | `7 passed` |

`ruff format` also checks Python code blocks inside Markdown files, so code examples in the documentation must be formatted too. Fix formatting with `uv run --locked ruff format .` and safe lint issues with `uv run --locked ruff check --fix .`.

## What the tests cover

| File | Checks |
| --- | --- |
| `tests/test_health.py` | `GET /health` returns `200` and exactly `{"status": "ok"}`; `POST /health` returns `405`; the OpenAPI schema has the version, the path and the required `status` field |
| `tests/test_config.py` | Default `app_name`; `.env` overrides the default; an environment variable overrides `.env` |
| `tests/test_version.py` | `app.__version__` matches `version` in `pyproject.toml` |

Tests call the application through FastAPI's `TestClient` (on `httpx2`): no network, no running server and no free port are needed.

Useful options:

```bash
uv run --locked pytest -k config
uv run --locked pytest -x
```

`-k config` runs tests whose names contain `config`; `-x` stops at the first failure.

## Lock file and dependency age

```bash
uv lock --check
```

The command fails if `uv.lock` does not match `pyproject.toml`; run `uv lock` and commit the updated file. The `[tool.uv] exclude-newer` date in `pyproject.toml` keeps `uv lock` from selecting PyPI releases published less than 14 days before it.

## Workflow file

The CI workflow can be linted locally with actionlint:

```bash
uvx --from actionlint-py actionlint .github/workflows/ci.yml
```

No output and exit code `0` mean no issues.

## Clean-clone check

To reproduce what CI does on a fresh machine, clone the repository into a temporary directory and run the checks there:

```bash
git clone . /tmp/ai-data-analyst-check
cd /tmp/ai-data-analyst-check
uv sync --locked
uv run --locked pytest
```

Recorded results of every check are in the [verification report](../VERIFICATION.md).
