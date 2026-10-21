# Streamlit interface

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Use the browser dashboard, ask the analyst and download stored reports.
The walkthrough in Russian is in [Stage 08](../STAGE_08.md); design decisions
are in [ADR 0008](../adr/0008-streamlit-interface.md).

## Start

Prepare PostgreSQL, migrations and a dataset as in [Quickstart](quickstart.md).
Install locked dependencies, then keep these commands running in two terminals
from the project root:

```bash
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
uv run python -m streamlit run ui/main.py --server.address 127.0.0.1
```

Open <http://127.0.0.1:8501>. Check <http://127.0.0.1:8000/ready> if the UI
reports that the API or database is unavailable. The interface does not start
the API or migrate the database. Launching through `python -m streamlit` keeps
the project root on the import path for the `ui` and `app` packages.

## Settings

| Variable | Purpose |
| --- | --- |
| `UI_API_URL` | Backend URL; default `http://127.0.0.1:8000` |
| `UI_REQUEST_TIMEOUT_SECONDS` | Network waiting timeout; default `150` seconds, range `1`–`600` |

Environment variables override `.env`. Restart Streamlit after changes.
The backend URL must use HTTP or HTTPS and `localhost`, `127.0.0.1` or `[::1]`.
Credentials, query parameters, fragments and paths other than `/` are rejected.
The client does not follow redirects, use environment proxies or retry requests.
Keep both processes bound to loopback while authentication is absent. Configure the OpenAI key only for the backend,
as described in [AI analyst](agent.md).

For a different API port:

```bash
UI_API_URL=http://127.0.0.1:8001 \
  uv run python -m streamlit run ui/main.py --server.address 127.0.0.1
```

## Dashboard

Choose `Dashboard` in the sidebar. Select current and comparison dates, choose
`category` or `region` and click `Load dashboard`. Editing fields alone does not
refresh a submitted result. Dates use the half-open Moscow interval `[start, end)`: September is `2026-09-01` to
`2026-10-01`. For the full generated dataset, compare it with August,
`2026-08-01` to `2026-09-01`.

Revenue, refunds, paid orders, average order value and contributions come
from the existing metrics and analytics API. Money stays exact in cards,
tables and JSON; chart coordinates are presentation values with exact source
values preserved. Undefined percentages and averages remain absent. Individual
dashboard requests may observe different snapshots if the data changes. A
separate anomaly form defaults to January–September 2026 and seed `42`.

## Analyst and history

Choose `AI analyst` and ask a complete question, for example
`Why did revenue fall in September 2026?`.
Each submission creates an independent `POST /api/agent/runs`; previous questions
are not automatically passed to the next run. The default provider is `mock`,
a deterministic planner over real analytics tools, without a model request.

Read facts, hypotheses, limitations, evidence references and tool calls. Open
a stored run from history and download its JSON. The current chat retains the
latest 20 entries in session memory; durable history uses pages of 10 records. A displayed trace does not
prove causation; the evidence checker has the limits described in
[AI analyst](agent.md).

## Reports

On `Dashboard`, explicitly save a comparison using both periods and a category
or regional dimension, or an anomaly report using a period and seed. Saving
recomputes the result through `POST /api/reports` and displays the returned
snapshot; it may differ from a dashboard loaded earlier. Open `Reports` to
browse saved snapshots with pagination. Full-month anomaly methods skip partial
months. Reports are frozen snapshots: a saved result
stays unchanged when new sales are loaded. Open history and download the
selected report as JSON, including exact monetary strings. Downloads use the
submitted parameters stored with the displayed result; unsubmitted edits do not
relabel a previous result.

## Errors and verification

The client shows fixed public messages for connection errors, timeouts, invalid
requests and backend failures. It does not display raw backend error bodies or
tracebacks. Creation requests are not retried automatically. After a timeout,
check history before resubmitting: backend work may have continued. The network
waiting timeout is not a guaranteed total request deadline or cancellation.

Verify dashboard values against the same API query, submit a `mock` run,
reopen its history, create both report kinds and check the downloaded JSON.
Reloading the page must not create another result without explicit submission.
Stop the API and confirm a safe error message. Actual test outcomes and the
separate remote CI status are recorded in [VERIFICATION.md](../VERIFICATION.md).
