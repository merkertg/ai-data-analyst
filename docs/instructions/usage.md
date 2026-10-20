# Using the API

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Endpoints available after Stage 01 and how to call them. Start the server with the [quickstart](quickstart.md) first. Metrics and analytics endpoints (`/api/metrics/*`, `/api/analytics/*`) are added in Stage 06.

## Endpoints

| Method and path | Purpose | Response |
| --- | --- | --- |
| `GET /health` | Liveness: the process is up and answers HTTP | `200` and `{"status":"ok"}` |
| `GET /docs` | Swagger UI, interactive documentation | HTML page |
| `GET /redoc` | ReDoc, read-only documentation | HTML page |
| `GET /openapi.json` | Machine-readable OpenAPI schema | JSON document |

`/health` does not check a database: there is none yet. A separate readiness check that includes PostgreSQL is planned for Stage 02.

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

## Use the interactive documentation

1. Open <http://127.0.0.1:8000/docs>.
2. Expand `GET /health`, press **Try it out**, then **Execute**.
3. The response shows code `200` and the JSON body.
4. Under **Schemas**, expand `HealthResponse` to see the response model.

## Read the OpenAPI schema

```bash
curl http://127.0.0.1:8000/openapi.json
```

The `info` block contains the title from `APP_NAME` and the version from `app/__init__.py`; `components.schemas.HealthResponse` describes the response model.

## Status codes you may see

| Code | When |
| --- | --- |
| `200 OK` | Successful `GET /health` |
| `404 Not Found` | Unknown path, for example `GET /nope`, body `{"detail":"Not Found"}` |
| `405 Method Not Allowed` | Wrong method, for example `POST /health`; the `allow: GET` header lists allowed methods |
| `500 Internal Server Error` | Server-side error, including a response that fails its schema |
