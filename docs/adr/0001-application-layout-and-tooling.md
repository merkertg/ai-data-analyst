# ADR 0001: Application layout and tooling

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The project is a single deployable web service, not a library. The course
plan uses an `app/` package at the repository root and `uvicorn app.main:app`.
uv 0.12 `uv init` defaults to a packaged `src/` layout with a build backend.
Starlette 1.7 deprecates `httpx` as the TestClient transport in favour of
`httpx2`.

## Decision

- Create the project with `uv init --app --no-package`: dependencies are
  installed into `.venv`, the project itself is not built or installed.
- Keep the code in `app/` at the root and add the root to pytest's import
  path with `[tool.pytest.ini_options] pythonpath = ["."]`.
- Lock all dependencies in `uv.lock`, install them in CI with
  `uv sync --locked`, and only accept PyPI releases at least 14 days old via
  `[tool.uv] exclude-newer`.
- Use Ruff (rules `E`, `F`, `I`, `UP`, `B`) and mypy in strict mode with the
  Pydantic plugin; run all checks in GitHub Actions with SHA-pinned actions.
- Use `httpx2` as the test HTTP client.

## Consequences

- No build step and no `[build-system]`; imports work for Uvicorn (adds the
  working directory) and pytest (configured `pythonpath`).
- If the code is ever needed as an installable package, switch to a packaged
  layout and drop the `pythonpath` setting.
- The `exclude-newer` date must be moved forward deliberately when updating
  dependencies.
