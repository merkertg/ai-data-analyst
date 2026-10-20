# CI and delivery

[← README](../../README.md) · [All documentation](../../README.md#documentation)

What GitHub Actions runs for this repository and how to read the result. The full explanation in Russian is in the [CI/CD guide](../CI_CD.md).

The workflow `CI` in `.github/workflows/ci.yml` runs on every push to `main`, every pull request targeting `main`, and on manual dispatch. There is no delivery yet: Docker images and their publication are added in Stage 10. Today the workflow only checks the code.

```text
push to main / pull request / manual run
                  ↓
Lint, types and tests (ubuntu-24.04, up to 10 minutes)
  checkout → uv 0.12.23 + Python 3.12 → uv sync --locked
  → ruff check → ruff format --check → mypy app tests → pytest
```

## Job and steps

| Step | Command | Fails when |
| --- | --- | --- |
| Checkout repository | `actions/checkout` | — |
| Install uv | `astral-sh/setup-uv`, uv 0.12.23, Python 3.12 | — |
| Install locked dependencies | `uv sync --locked` | `uv.lock` does not match `pyproject.toml` |
| Ruff lint | `uv run --locked ruff check .` | Style, import order or common bug patterns |
| Ruff format | `uv run --locked ruff format --check .` | A Python file or Markdown code block is not formatted |
| Mypy | `uv run --locked mypy app tests` | A type error in strict mode |
| Pytest | `uv run --locked pytest` | Any test fails |

## Security settings

- `permissions: contents: read` — the job can only read the repository.
- Actions are pinned by full commit SHA with the version in a comment, for example `actions/checkout@3d3c42e… # v7.0.1`. A tag can be moved to other code; a SHA cannot.
- `persist-credentials: false` — the GitHub token is not left in the working directory after checkout.
- `concurrency` cancels an outdated run when a pull request gets a new push; runs on `main` are not cancelled.

## Where to see the result

Open the repository on GitHub → **Actions** → workflow **CI** → the run for your commit. The job is called **Lint, types and tests**. A green check means every step passed. If a step is red, open it, read the log, reproduce the same command locally from [testing](testing.md), fix it and push again.

Local checks do not confirm a remote run. The confirmed status of each commit is recorded in the [verification report](../VERIFICATION.md).
