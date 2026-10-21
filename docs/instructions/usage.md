# Using the API

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Endpoints after Stage 06 and how to call them. Start PostgreSQL, apply migrations (head is `0002`), load data and start the server with the [quickstart](quickstart.md) first. The detailed explanation in Russian is in the [Stage 06 guide](../STAGE_06.md).

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Liveness: the process is up |
| `GET /ready` | Readiness: PostgreSQL reachable and schema at the latest migration |
| `GET /api/metrics/revenue` | Paid sales, refunds, net revenue, monthly buckets, optional comparison |
| `GET /api/metrics/orders` | Paid orders and average order value, monthly buckets, optional comparison |
| `GET /api/analytics/categories` | Net revenue change between two periods and each category's share |
| `GET /api/analytics/regions` | The same by customer region |
| `GET /api/analytics/anomalies` | Stage 05 anomaly candidates for a period |
| `POST /api/reports` | Compute and save a comparison or anomaly report |
| `GET /api/reports/{report_id}` | A saved report exactly as stored |
| `GET /api/reports` | Saved reports, newest first, without result bodies |
| `GET /docs`, `GET /redoc`, `GET /openapi.json` | Interactive and machine-readable documentation |

All analytics routes are read-only (`REPEATABLE READ READ ONLY`) except `POST /api/reports`. There is no authentication yet: run the server on `127.0.0.1` only. Access control arrives in Stage 09.

## Parameters

Periods are half-open Moscow date intervals `[start, end)`: `start=2026-09-01&end=2026-10-01` is September.

| Parameter | Routes | Rules |
| --- | --- | --- |
| `start`, `end` | all analytics routes | Required ISO dates, `start < end`, at most 120 calendar months |
| `compare_start`, `compare_end` | `revenue`, `orders` (optional); `categories`, `regions` (required) | Same rules; both or neither |
| `seed` | `anomalies` | Integer 0–4294967295, default `42` |
| `limit`, `offset` | `GET /api/reports` | `limit` 1–100 (default 20), `offset` ≥ 0 |

Unknown query parameters are rejected with 422.

## Examples

```bash
B=http://127.0.0.1:8000
curl "$B/api/metrics/revenue?start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
curl "$B/api/metrics/orders?start=2026-09-01&end=2026-10-01"
curl "$B/api/analytics/categories?start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
curl "$B/api/analytics/regions?start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
curl "$B/api/analytics/anomalies?start=2026-01-01&end=2026-10-01&seed=42"
```

Verified on the seed 42 demo dataset (20,000 orders): September vs August net revenue `-165497371.86` (`-26.18`%), pumps account for `83.75`% of the decline, and the detector returns 33 candidates. Money values are JSON strings, for example `"466678757.35"`; undefined values (AOV without orders, a percentage of a zero baseline) are `null`. Every response states `"currency": "RUB"` and `"timezone": "Europe/Moscow"`.

## Saved reports

```bash
curl -i -X POST "$B/api/reports" \
  -H 'Content-Type: application/json' \
  -d '{"kind":"comparison","start":"2026-09-01","end":"2026-10-01","compare_start":"2026-08-01","compare_end":"2026-09-01","dimension":"category"}'
```

The answer is `201 Created` with `location: /api/reports/<uuid>` and the stored report: `id`, `kind`, `created_at`, `app_version`, `parameters` and `result`. An anomaly report uses `{"kind":"anomalies","start":"2026-01-01","end":"2026-10-01","seed":42}`.

```bash
curl "$B/api/reports/<uuid>"
curl "$B/api/reports?limit=10&offset=0"
```

A report is a snapshot: it is computed once and never recomputed, so it keeps describing the data at the time it was saved. Reports are stored in the `reports` table added by migration `0002`.

## Check readiness

```bash
curl -i "$B/ready"
```

| Situation | Response |
| --- | --- |
| Database running, migrations applied | `200` `{"status":"ready","revision":"0002"}` |
| `docker compose stop db` | `503` `{"detail":"Database is not ready"}` |
| Database started again | `200` — the pool reconnects without restarting the API |

`/health` never touches the database; use it to decide whether to restart a process and `/ready` to decide whether to send it traffic.

## Status codes

| Code | When |
| --- | --- |
| `200 OK` | Successful read |
| `201 Created` | Report saved; see the `location` header |
| `404 Not Found` | Unknown path, or an unknown report UUID (`{"detail":"Report not found"}`) |
| `405 Method Not Allowed` | Wrong method, for example `POST /health` |
| `422 Unprocessable Content` | Invalid parameters or body; the database is not touched |
| `500 Internal Server Error` | Unexpected server error, without details |
| `503 Service Unavailable` | `DATABASE_URL` not set or the database unreachable (`{"detail":"Database is not ready"}`) |

The 503 text is the same for every cause: the database address and driver errors never reach the client.
