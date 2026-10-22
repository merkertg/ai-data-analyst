# ADR 0010: Docker packaging, demo bootstrap and image delivery

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

The course goal for Stage 10 is that another developer can clone the repository, run `docker compose up --build`, open the interface and reproduce the demonstration scenarios. Until now the database ran in Compose while migrations, data loading, token issuing, the API and Streamlit were started by hand. The plan also asks for coverage in CI, a dependency audit, a Docker build with a smoke test and publication of the image after successful checks.

## Decision

- **One runtime image** built in two stages: a builder with uv 0.12.23 installs `uv sync --locked --no-dev` into `.venv`; the final stage on `python:3.12-slim` (both pinned by digest) copies `.venv`, `app/`, `ui/`, migrations and the eval questions and runs as UID 10001. Migrations, bootstrap, API and interface share all dependencies, so one image with different commands replaces the separate UI image of the first project.
- **Compose stand** with `db`, `migrate`, `bootstrap`, `api` and `ui`, ordered by health and completion conditions. All ports bind to `127.0.0.1` (API 8001, UI 8502, database 5436). Defaults let the stand start without `.env`; the default database password is for a local demo only.
- **Idempotent bootstrap** (`python -m app.bootstrap`): requires the latest migration, loads the seed 42 bundle only into an empty database (`DEMO_DATA=false` skips it) and keeps one valid analyst token for the interface in a `0600` file on a dedicated volume, replacing it only when it no longer authenticates.
- **Interface in a container:** `UI_API_URL` may name a host other than loopback only if that host is listed in `UI_ALLOWED_API_HOSTS`, which accepts single-label names only (no domains or IP addresses). The token is read from `UI_API_TOKEN_FILE`, mounted read-only. The UI service gets no database address and no model key.
- **CI/CD:** coverage of `app/` and `ui/` (lines and branches) must stay ≥ 90 %; a blocking pip-audit of the locked runtime dependencies with explained exceptions that expire within 30 days and fail when stale; an image build with a runtime-contract check; `docker compose up` with `scripts/smoke_stack.py` before and after container re-creation; publication of the very image that passed the smoke test to GHCR (`:main`, `:sha-…`, `:vX.Y.Z` for tags on `main`), with `packages: write` only in that job.
- **Security fixes versus the 14-day age policy:** fixes for Pillow (24 CVEs) and certifi are younger than 14 days and Pillow 13 also needs a newer Streamlit. The age policy is kept; the findings are accepted until 6 November 2026 with reasons (no image decoding in this project; one distrusted root certificate for a fixed OpenAI host) and a dated update plan.

## Consequences

- One command starts a working, populated and authenticated stand; repeated starts change nothing.
- The image is about 1 GB because scikit-learn, Pandas, PyArrow and Streamlit are heavy; the interface container carries server code it does not run.
- Only amd64 is built and published in CI; Apple Silicon builds arm64 locally. Images are not signed and no SBOM is attached yet.
- Accepted vulnerabilities stay visible and expire; the audit fails on 7 November unless the planned update happens.
- The stand is local: there is no HTTPS, rate limits live in one process and the default password must be replaced for anything beyond a demo.
