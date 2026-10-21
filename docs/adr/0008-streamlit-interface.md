# ADR 0008: Streamlit interface over the existing HTTP API

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

The API already exposes exact metrics, category and regional contributions,
anomaly detection, saved report snapshots and independent agent investigations.
The next stage needs a usable local interface with charts and downloadable
results without duplicating analytics or adding a second route to the database.
Financial values must remain deterministic SQL/Decimal outputs.

## Decision

- **A separate Streamlit process.** `ui/main.py` is the entry point, started
  with `uv run python -m streamlit run ui/main.py --server.address 127.0.0.1`. FastAPI
  continues to run separately on `127.0.0.1:8000`. Python on the Streamlit
  server calls the existing HTTP routes; the browser does not query PostgreSQL.
- **Configuration owned by the UI.** `UI_API_URL` and
  `UI_REQUEST_TIMEOUT_SECONDS` are read from environment variables and `.env`.
  Environment variables take priority. The base URL accepts HTTP/HTTPS on
  `localhost`, `127.0.0.1` or `[::1]` and rejects embedded credentials, query
  parameters, fragments and paths other than `/`. The timeout defaults to 150
  seconds and accepts 1–600 seconds.
  Database configuration and model credentials are not UI inputs.
- **Small UI modules.** `ui/config.py` validates settings; `ui/client.py` uses
  standard-library `urllib`, existing typed API response schemas, no redirects,
  no environment proxy handling and no automatic retries; `ui/charts.py` builds
  Plotly figures. Sidebar navigation selects `Dashboard`, `AI analyst` or
  `Reports` so only the selected page performs its relevant work.
- **Reuse the existing contracts.** Dashboard requests use
  `/api/metrics/revenue`, `/api/metrics/orders`, `/api/analytics/categories`
  and `/api/analytics/regions`. Questions and history use `/api/agent/runs`;
  snapshots use `/api/reports`. Stage 08 does not require a schema migration
  or change how the backend computes financial metrics.
- **Presentation-only charts.** Plotly draws monthly revenue and signed group
  contributions from API results. Floating-point chart coordinates are only
  visual positions; cards, tables, exact hover text and JSON preserve source
  monetary values. The UI does not recompute financial totals or percentages.
  Missing averages and undefined percentages are not replaced with zeros.
- **Explicit creation actions.** Streamlit reruns must not resubmit a completed
  question or report creation automatically. New POST requests follow explicit
  user submission. Successful responses and selected history items can be
  displayed again and downloaded without creating new records. Submitted
  parameters are stored with the displayed result so editing an unsubmitted
  form cannot relabel an export. Saving a report explicitly recomputes it through
  the API and displays the returned snapshot, rather than pretending to persist
  an earlier multi-request dashboard unchanged.
- **Independent investigations.** The chat-shaped UI submits one complete
  question per agent run. Stored history is for inspection, not implicit
  conversational memory. The provider and model are visible so a mock run is
  distinguishable from a real model request.
- **Safe failure presentation.** Network failures, timeouts and HTTP failures
  map to fixed public messages. Raw backend error bodies and exception text
  are not rendered. Mutation requests are not retried automatically.
- **JSON export.** Downloads contain the API response, including parameters,
  identifiers, evidence and exact monetary strings. A generated PDF report
  for each investigation is outside this stage.

## Consequences

- The UI and backend have one financial source of truth, and HTTP client and
  rendering behaviour can be tested with fake responses without a database
  or an OpenAI key. End-to-end local checks remain a separate form of evidence.
- Users must run PostgreSQL, FastAPI and Streamlit; a page loading successfully
  does not imply database readiness. The client must handle an unavailable API
  and a `503` readiness state without exposing backend details.
- A network waiting timeout is not a guaranteed total HTTP deadline. It only
  stops the UI waiting when the transport times out; it does not prove
  cancellation of
  an in-flight backend operation. Users should inspect history before resending
  a question. Explicit creation actions reduce accidental duplicates but do not
  make the API idempotent.
- Dashboard endpoints are independent requests and can observe different
  snapshots while data changes. Stored reports retain the backend snapshot
  behaviour from ADR 0006; a multi-request dashboard is not one database
  transaction.
- This is a local learning interface. Loopback binding is the current operating
  constraint, not a replacement for authentication, authorization, rate limiting
  or a production deployment design.
- The evidence checker and model limitations from ADR 0007 still apply.
  Presenting a checked report or a chart does not establish a causal explanation
  or demonstrate that a real OpenAI model was tested.
