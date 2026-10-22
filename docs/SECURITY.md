# Security

[← README](../README.md) · [All documentation](../README.md#documentation)

What the application protects, how, and what is still open. The detailed Russian walkthrough is in the [Stage 09 guide](STAGE_09.md); the decision record is [ADR 0009](adr/0009-access-control-and-agent-evals.md). Token management is described in [Access tokens](instructions/security.md).

## Assets and threats

| Asset | Threat | Control |
| --- | --- | --- |
| Sales data | Anonymous reads | Bearer token on every `/api` route |
| Sales data | Modification through the API or the agent | No write tools; read routes and tools run `REPEATABLE READ READ ONLY`; tool SQL is fixed and parameterised |
| Database availability | Heavy queries | `statement_timeout` (15 s default) on every application connection; agent periods at most 24 months, API at most 120 months |
| LLM budget | Many agent runs | Analyst role required; 6 runs per minute per token |
| API tokens | Theft of the database | Only the SHA-256 and a 12-character prefix are stored |
| API tokens | Guessing or probing | 256-bit random tokens; one identical 401 for missing, malformed, unknown, revoked and expired tokens |
| OpenAI key | Leak through errors or history | `SecretStr`, fixed base URL, SDK errors replaced by fixed public messages; tests check stored runs and responses |
| Evaluation answer key | The agent reading the answers | No runtime module mentions `ground_truth`; agent tools have no file access |
| Report integrity | Invented or injected numbers | Evidence check: every cited value must match a tool result and every written number must match verified evidence |

## Access control

| Role | Allowed |
| --- | --- |
| `viewer` | `GET` metrics, analytics, saved reports, agent history |
| `analyst` | Everything a viewer may, plus `POST /api/reports` and `POST /api/agent/runs` |

`/health`, `/ready`, `/docs`, `/redoc` and `/openapi.json` are open; they contain no business data. Tokens are issued, listed and revoked only with `python -m app.security` on the server, which needs direct database access; there is no token API. Revocation and expiry apply from the next request. A malformed token is rejected before any SQL.

## Rate limits

| Setting | Default | Route |
| --- | --- | --- |
| `AGENT_RUNS_PER_MINUTE` | 6 | `POST /api/agent/runs` |
| `REPORTS_PER_MINUTE` | 30 | `POST /api/reports` |

A sliding 60-second window per token; over the limit the API answers `429` with `Retry-After`. Counters live in the memory of one API process.

## Agent safety

The model chooses among nine registered read-only tools; it cannot run SQL. Arguments are validated by strict Pydantic models before SQL (unknown fields, coerced types, duplicate JSON keys, bad periods). Tool results and the question are treated as data in the system prompt. Whatever the model writes, the runtime rejects a report whose cited values differ from tool results or whose numbers have no evidence, and stops every run after fixed limits of steps, calls, corrections, time and context.

## Tests

`tests/security/` attacks the running application: bad, revoked and expired tokens, viewer writes, rate limits, every `/api` path without a token, six SQL injection payloads in tool arguments, writes in tool sessions, a long query against the timeout, token storage, a hostile scripted model (forbidden tools, SQL in arguments, oversized limits, a file path as a category, invented report numbers), a prompt-injection number planted in data, and an OpenAI error message containing the key. All 55 tests pass; see [VERIFICATION.md](VERIFICATION.md).

## Known limits

- No HTTPS: run the API on `127.0.0.1` or behind a TLS proxy (Stage 10).
- Rate limits are per process; several API processes need a shared store.
- No audit trail of who saved which report or asked which question.
- No separate read-only PostgreSQL role; protection relies on read-only transactions and fixed queries.
- The evidence check verifies numbers, not causal claims or wording.
- A real OpenAI model has not been evaluated; prompt-injection resistance of the model itself is unmeasured.
