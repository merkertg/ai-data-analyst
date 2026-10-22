# Windows and PowerShell

[← README](../../README.md) · [All documentation](../../README.md#documentation)

How to run the project on Windows. **Windows is not checked in CI**: the stand is verified on macOS (arm64, locally) and Linux (amd64, GitHub Actions). The recommended path on Windows is Docker Desktop, where the containers run Linux and behave exactly as in CI.

## Install the tools

- [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with the WSL 2 backend.
- Git for Windows, to clone the repository.
- Python 3 only if you want to run `scripts/smoke_stack.py` from the host.

## Start the stand

The Compose commands are the same in PowerShell:

```powershell
git clone git@github.com:merkertg/ai-data-analyst.git
cd ai-data-analyst
docker compose up --build --detach --wait --wait-timeout 300
```

Open <http://127.0.0.1:8502> for the interface and <http://127.0.0.1:8001/docs> for the API. Stop with `docker compose down`; add `--volumes` to delete the data.

## Bash constructs and their PowerShell equivalents

| Bash | PowerShell |
| --- | --- |
| `TOKEN="$(docker compose exec -T ui cat /run/ai-data-analyst/ui_token)"` | `$token = docker compose exec -T ui cat /run/ai-data-analyst/ui_token` |
| `export SMOKE_TOKEN=…` | `$env:SMOKE_TOKEN = $token` |
| `curl -H "Authorization: Bearer $TOKEN" URL` | `Invoke-RestMethod -Uri URL -Headers @{ Authorization = "Bearer $token" }` |
| Line continuation `\` | Line continuation `` ` `` |
| `API_PORT=8011 docker compose up` | `$env:API_PORT = "8011"; docker compose up` |

## Typical commands

```powershell
$token = docker compose exec -T ui cat /run/ai-data-analyst/ui_token
$env:SMOKE_TOKEN = $token
python scripts/smoke_stack.py

$query = "start=2026-09-01&end=2026-10-01&compare_start=2026-08-01&compare_end=2026-09-01"
Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/metrics/revenue?$query" `
  -Headers @{ Authorization = "Bearer $token" }

$body = @{ question = "Why did revenue fall in September?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/agent/runs" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" -Body $body
```

Token management runs inside the API container, so it is the same command on every system:

```powershell
docker compose exec -T api python -m app.security issue --name "me" --role analyst
```

## Development without Docker

Running Python, PostgreSQL and the tests directly on Windows is not verified. Use WSL 2 (Ubuntu) and follow the [quickstart](quickstart.md) inside it; the commands are the Linux ones.
