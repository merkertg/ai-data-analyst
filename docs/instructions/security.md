# Access tokens

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Every `/api` route needs `Authorization: Bearer <token>`. `/health`, `/ready` and the documentation pages stay open. The threat model is in [Security](../SECURITY.md); the Russian walkthrough is in the [Stage 09 guide](../STAGE_09.md).

## In the Docker stand

`docker compose up` issues an analyst token for the interface automatically and keeps it in the `ui_token` volume. Other tokens are issued inside the API container:

```bash
docker compose exec -T api python -m app.security issue --name "me" --role viewer --days 7
docker compose exec -T api python -m app.security list
```

## Issue a token

Apply migrations first (head is `0004`). Token management talks to the database from `DATABASE_URL` directly; there is no HTTP endpoint for it.

```bash
uv run python -m app.security issue --name "Streamlit" --role analyst --days 90
```

The command prints the id, role, expiry and the token. **Copy the token now**: only its SHA-256 and first 12 characters are stored, so it cannot be shown again.

| Role | Allowed |
| --- | --- |
| `viewer` | Read metrics, analytics, saved reports and agent history |
| `analyst` | Also save reports and ask the agent |

`--days` is optional; without it the token does not expire.

## Use a token

```bash
TOKEN='ida_…'
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/reports"
```

For the Streamlit interface, put the token in `.env` and restart Streamlit:

```bash
UI_API_TOKEN=ida_…
```

Never commit `.env` or paste tokens into issues, logs or screenshots.

## List and revoke

```bash
uv run python -m app.security list
uv run python -m app.security revoke <token-id>
```

`list` shows ids, prefixes, roles, state and expiry, never the token. A revoked or expired token gets `401` from the next request.

## Answers

| Code | Meaning |
| --- | --- |
| `401` | Missing, malformed, unknown, revoked or expired token — the same answer for all |
| `403` | A viewer tried to save a report or ask the agent |
| `429` | Over `AGENT_RUNS_PER_MINUTE` (default 6) or `REPORTS_PER_MINUTE` (default 30) for this token; wait `Retry-After` seconds |

## Related settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_STATEMENT_TIMEOUT_MS` | 15000 | PostgreSQL cancels any application statement running longer |
| `AGENT_RUNS_PER_MINUTE` | 6 | Agent runs per token per minute |
| `REPORTS_PER_MINUTE` | 30 | Saved reports per token per minute |
| `UI_API_TOKEN` | empty | Token the Streamlit client sends |
