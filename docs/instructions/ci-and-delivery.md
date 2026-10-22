# CI and delivery to GHCR

[← README](../../README.md) · [All documentation](../../README.md#documentation)

What GitHub Actions runs for this repository, how the tested image reaches the GitHub Container Registry and how to read the result. The full explanation in Russian is in the [CI/CD guide](../CI_CD.md); versions and publication are in [RELEASES.md](../RELEASES.md).

The workflow `CI` in `.github/workflows/ci.yml` runs on every push to `main`, every push of a `v*` tag, every pull request targeting `main` and on manual dispatch.

```text
push / pull request / tag v1.2.3
 ├─ Lint, types and tests        (PostgreSQL service, coverage ≥ 90 %)
 ├─ Audit runtime dependencies   (pip-audit over uv.lock, dated exceptions)
 └─► Build and smoke test Docker (needs both)
        image build → runtime contract → docker compose up → smoke
        → down + up → smoke again → save the tested image (push only)
     └─► Publish tested image to GHCR (push only)
           main → :main, :sha-<commit>; v1.2.3 → :v1.2.3, :sha-<commit>
```

## Jobs

| Job | Main commands | Fails when |
| --- | --- | --- |
| Lint, types and tests | `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy app ui tests migrations`, `alembic upgrade/check/downgrade/upgrade`, `pytest --cov` | Style, types, a migration, any test, or line+branch coverage of `app/` and `ui/` below 90 % |
| Audit runtime dependencies | `python scripts/audit_dependencies.py` | A known vulnerability is not in `scripts/audit-exceptions.json`, an exception expired, or an exception no longer matches a finding |
| Build and smoke test Docker | `docker build`, runtime check, `docker compose up --no-build --wait`, `python3 scripts/smoke_stack.py`, `docker compose down`, `up` again | The image runs as root or contains pytest, Ruff, mypy or uv; a service is not healthy; a smoke check fails; data or the token did not survive re-creation |
| Publish tested image to GHCR | `docker load`, `docker tag`, `docker push` | The tag is not `vX.Y.Z` or not on `main`; the registry rejects the push |

The smoke check calls `/health` and `/ready` (revision `0004`), expects 401 without a token, compares the September revenue with the seed 42 values (`466678757.35`, change `-165497371.86`, `-26.18`%), asks the agent and finds the cited value in its evidence, finds the run in history and checks the Streamlit health endpoint.

## Security settings

- `permissions: contents: read` for the workflow; only the publish job has `packages: write`.
- Actions are pinned by full commit SHA with the version in a comment; a test checks that every `uses:` is pinned.
- PostgreSQL, Python and uv images are pinned by digest.
- `persist-credentials: false` — the GitHub token is not left in the working directory.
- The interface token of the CI stand is masked in the log and passed through the environment.
- The published image is the one that passed the smoke test; it is not rebuilt.
- Passwords in the workflow (`analyst_ci`, `container_ci`) belong to throwaway containers.

## Artifacts

| Artifact | Contents | Kept |
| --- | --- | --- |
| `coverage-report` | `coverage.xml` | 7 days |
| `dependency-audit` | Exported requirements and `pip-audit.json` | 7 days |
| `tested-image` | The tested image as `docker save` output (push only) | 1 day |

## Where to see the result

Open the repository on GitHub → **Actions** → workflow **CI** → the run for your commit. A green run shows four jobs (three on a pull request). The published image appears under **Packages** of the repository owner; the publish job summary lists its tags and digest.

Local checks do not confirm a remote run. The confirmed status of each commit is recorded in the [verification report](../VERIFICATION.md).
