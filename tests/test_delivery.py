"""Static checks of the delivery files: pinned images, local ports, no secrets."""

import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
COMPOSE = (ROOT / "compose.yaml").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
POSTGRES = re.compile(r"postgres:17@sha256:[0-9a-f]{64}")


def test_every_base_image_is_pinned_by_digest() -> None:
    """A tag can be moved to other contents; a digest cannot."""
    for line in DOCKERFILE.splitlines():
        if line.startswith("FROM "):
            image = line.split()[1]
            assert image == "python-base" or "@sha256:" in image, line
    assert re.search(r"COPY --from=ghcr\.io/astral-sh/uv:[\d.]+@sha256:", DOCKERFILE)


def test_postgres_digest_is_the_same_everywhere() -> None:
    """Compose and CI run exactly the same PostgreSQL image."""
    digests = set(POSTGRES.findall(COMPOSE)) | set(POSTGRES.findall(WORKFLOW))
    assert len(digests) == 1


def test_published_ports_listen_on_loopback_only() -> None:
    """No service of the stand is reachable from the local network."""
    ports = re.findall(r'-\s+"([^"]+:\d+)"', COMPOSE)
    assert ports
    assert all(port.startswith("127.0.0.1:") for port in ports), ports


def test_runtime_runs_as_a_fixed_non_root_user() -> None:
    """The final stage switches to UID 10001 and ships no uv or dev tools."""
    runtime = DOCKERFILE[DOCKERFILE.index("AS runtime") :]
    assert "useradd --uid 10001" in runtime and "\nUSER app" in runtime
    assert "/bin/uv" not in runtime
    assert "uv sync --locked --no-dev" in DOCKERFILE


def test_secrets_and_tests_stay_out_of_the_build_context() -> None:
    """.env files, Git data and tests are not sent to Docker."""
    for entry in (".env", ".env.*", ".git/", "tests/", "data/", "reports/"):
        assert entry in DOCKERIGNORE, entry
    assert "!.env.example" in DOCKERIGNORE


def test_the_interface_never_gets_the_database_or_the_model_key() -> None:
    """The ui service lists its own environment without DATABASE_URL."""
    ui = COMPOSE[COMPOSE.index("\n  ui:") : COMPOSE.index("\n  db-test:")]
    assert "DATABASE_URL" not in ui and "OPENAI_API_KEY" not in ui
    assert "UI_ALLOWED_API_HOSTS: api" in ui
    assert "ui_token:/run/ai-data-analyst:ro" in ui


def test_audit_exceptions_are_explained_and_temporary() -> None:
    """Each accepted vulnerability has a reason and a near expiry date."""
    data = json.loads(
        (ROOT / "scripts" / "audit-exceptions.json").read_text(encoding="utf-8")
    )
    reviewed = date.fromisoformat(data["reviewed"])
    for entry in data["exceptions"]:
        assert entry["reason"].strip() and entry["package"] and entry["id"]
        expires = date.fromisoformat(entry["expires"])
        assert reviewed <= expires <= reviewed + timedelta(days=30), entry["id"]


def test_actions_are_pinned_to_full_commit_shas() -> None:
    """Third-party actions run at an exact commit, never a movable tag."""
    uses = re.findall(r"uses:\s*(\S+)", WORKFLOW)
    assert uses
    assert all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", action) for action in uses), uses
