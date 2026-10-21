# Using the API

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Endpoints available after Stage 02 and how to call them. Start the database and the server with the [quickstart](quickstart.md) first. Stage 04 metrics are available through the read-only [analytics CLI](analytics.md), without starting this server. Metrics and analytics HTTP endpoints (`/api/metrics/*`, `/api/analytics/*`) are added in Stage 06.

## Endpoints

| Method and path | Purpose | Response |
| --- | --- | --- |
| `GET /health` | Liveness: the process is up and answers HTTP | `200` and `{"status":"ok"}` |
| `GET /ready` | Readiness: PostgreSQL is reachable and the schema matches the latest migration | `200` and `{"status":"ready","revision":"0001"}`, or `503` |
| `GET /docs` | Swagger UI, interactive documentation | HTML page |
| `GET /redoc` | ReDoc, read-only documentation | HTML page |
| `GET /openapi.json` | Machine-readable OpenAPI schema | JSON document |

## Check the service

```bash
curl -i http://127.0.0.1:8000/health
```

Verified response:

```text
HTTP/1.1 200 OK
server: uvicorn
content-length: 15
content-type: application/json

{"status":"ok"}
```

The response body follows the `HealthResponse` model: one required field `status` whose only allowed value is `"ok"`. If the code ever tried to return anything else, FastAPI would refuse to send it and answer `500` instead.

## Check readiness

```bash
curl -i http://127.0.0.1:8000/ready
```

Verified responses on a real server:

| Situation | Response |
| --- | --- |
| Database running, migrations applied | `200` `{"status":"ready","revision":"0001"}` |
| `docker compose stop db` | `503` `{"detail":"Database is not ready"}` |
| Database started again | `200` — the pool reconnects without restarting the API |

`503` is also returned when `DATABASE_URL` is not set, when the database is empty, or when its schema version differs from the latest migration in the code. The response never includes the database address or driver errors.

Use `/health` to decide whether to restart a process and `/ready` to decide whether to send it traffic.

## Use the interactive documentation

1. Open <http://127.0.0.1:8000/docs>.
2. Expand `GET /health` or `GET /ready`, press **Try it out**, then **Execute**.
3. Under **Schemas**, expand `HealthResponse` and `ReadyResponse` to see the response models.

## Read the OpenAPI schema

```bash
curl http://127.0.0.1:8000/openapi.json
```

The `info` block contains the title from `APP_NAME` and the version from `app/__init__.py`; `components.schemas` describes the response models; `/ready` lists both `200` and `503` responses.

## Status codes you may see

| Code | When |
| --- | --- |
| `200 OK` | Successful `GET /health` or `GET /ready` |
| `404 Not Found` | Unknown path, for example `GET /nope`, body `{"detail":"Not Found"}` |
| `405 Method Not Allowed` | Wrong method, for example `POST /health`; the `allow: GET` header lists allowed methods |
| `500 Internal Server Error` | Server-side error, including a response that fails its schema |
| `503 Service Unavailable` | `/ready`: database not configured, unreachable, empty or outdated |
