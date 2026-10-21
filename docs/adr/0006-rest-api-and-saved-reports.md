# ADR 0006: REST API and saved reports

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

Stages 04–05 expose exact metrics and anomaly detection as Python functions and CLIs. The Streamlit interface (Stage 08) and the AI agent (Stage 07) need the same results over HTTP, in one JSON format, without re-implementing any arithmetic. The course plan also asks for saved reports that can be read back by id.

## Decision

- Add thin FastAPI routers in `app/api/` (`metrics`, `analytics`, `reports`) over response-building services in `app/services/`. Services only arrange results of `app/analytics`; no route or service computes money itself.
- Describe query parameters as Pydantic models (`PeriodQuery`, `OptionalComparisonQuery`, `ComparisonQuery`, `AnomalyQuery`) with `extra="forbid"` and model validators: half-open Moscow periods, start before end, at most 120 calendar months, comparison bounds given together, seed within 32 bits. Invalid input is a 422 before any SQL.
- Inject sessions with `Depends`: `ReadSession` for every GET is a `REPEATABLE READ READ ONLY` snapshot; `WriteSession` for `POST /api/reports` commits explicitly in the route. Both are `LazySession` objects that resolve the engine on the first statement, because FastAPI resolves dependencies even when parameter validation fails; an invalid request must neither touch the database nor turn into a 503.
- Serialise money as JSON strings through Pydantic `Decimal` fields and undefined values as `null`. Response models read core dataclasses with `from_attributes=True`.
- Map `DatabaseNotConfigured`, `OperationalError` and `InterfaceError` to one 503 text without the address or driver message. Unknown report ids return 404; other failures keep FastAPI's default 500 without details.
- Store reports in a new `reports` table (migration `0002`): UUID primary key, `kind` checked against `comparison`/`anomalies`, request `parameters` and API-shaped `result` as JSONB, `app_version` and `created_at`. A report is an immutable snapshot with no foreign keys to sales rows. `POST /api/reports` selects the request model by a `kind` discriminator.
- Do not add authentication yet: the API is bound to `127.0.0.1` for local use. Access control is part of Stage 09.

## Consequences

- The HTTP layer, the CLI and the future agent share one implementation; integration tests assert that API numbers equal the core functions.
- Saved reports remain unchanged when data changes; reproducing one requires the same data, parameters and code version.
- Anomaly detection runs on every GET request (about 0.2 s on 20,000 orders); saving it as a report avoids recomputation.
- Report listings have no total count and reports cannot be deleted through the API yet.
- Exposing the API beyond localhost requires the Stage 09 security work first.
