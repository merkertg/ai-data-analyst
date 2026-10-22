# ADR 0009: Access control, SQL limits and agent evaluations

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Until Stage 08 every `/api` route was open and the documentation asked to run the API on `127.0.0.1` only. The agent can call a paid model, and saving reports runs the anomaly detector. The agent's answers were tested on individual examples, but there was no repeatable measurement of answer quality. The course plan asks for unit, integration, agent-eval and security checks and for 30–50 questions with answers computed independently of the LLM.

## Decision

- **Bearer API tokens in PostgreSQL.** Table `api_tokens` (migration `0004`) stores a name, a role, the SHA-256 of the token, a 12-character prefix, an optional expiry and a revocation time. Tokens are `ida_` plus 32 random bytes and are shown once. A fast hash is sufficient because tokens are high-entropy; slow password hashing is not needed. Tokens are managed only with `python -m app.security` (issue, list, revoke) on the server.
- **Two roles.** `viewer` reads; `analyst` may also `POST /api/reports` and `POST /api/agent/runs`. All `/api` routers depend on `get_principal`; missing, malformed, unknown, revoked and expired tokens get one identical 401, and malformed tokens are rejected before SQL. Health, readiness and documentation stay open.
- **Per-token rate limits** for the two costly POST routes: an in-process sliding 60-second window, 429 with `Retry-After`.
- **SQL limits.** A `statement_timeout` (default 15 s) is set when every application connection opens. Existing controls remain: fixed parameterised tool queries, read-only snapshot transactions, period bounds.
- **The Streamlit client** sends `UI_API_TOKEN` and maps 401, 403 and 429 to specific messages.
- **Agent evals.** 42 questions in `evals/cases.json` describe what a correct answer must cite. A Pandas oracle (`app/evals/oracle.py`) computes expected values from the CSV bundle in integer kopecks, independently of PostgreSQL and the analytics core. A reference provider answers each case with recorded tool calls to validate the set; the production runtime and evidence check run every case; scores cover completion, language, tool choice, cited values, refusals and planted numbers. `python -m app.evals` runs a provider against a database holding the same bundle; CI runs the reference and mock providers on the seed 42 bundle in the `*_test` database.
- **Shared test fixtures.** Database fixtures move to `tests/conftest.py`; any test using the test database is marked `integration`. New folders `tests/security/` and `tests/evals/` follow the course structure. A test analyst principal is injected by default; tests marked `real_auth` use real tokens.

## Consequences

- The API can be exposed beyond localhost only together with HTTPS (Stage 10); tokens travel in a header.
- Rate counters reset on restart and are not shared between processes.
- Pandas becomes a declared dependency; it was already locked through Streamlit.
- The reference run proves that SQL tools and an independent implementation agree on 42 values; it says nothing about a language model, which still needs to be measured with `--provider openai`.
- The mock passes 17 of 42 questions and never refuses; this baseline is recorded so behaviour changes are noticed.
- There is no audit trail of who saved which report, and no separate read-only database role.
