"""Token format, rate limits and the token CLI."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api import dependencies
from app.api.rate_limit import RateLimiter
from app.main import app
from app.security import __main__ as cli
from app.security.tokens import (
    Principal,
    Role,
    is_well_formed,
    new_token,
    token_hash,
)


def test_new_tokens_are_random_and_well_formed() -> None:
    """32 random bytes behind a recognisable prefix; no two tokens alike."""
    tokens = {new_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(is_well_formed(token) and len(token) == 47 for token in tokens)
    assert all(len(token_hash(token)) == 64 for token in tokens)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "ida_",
        "ida_" + "a" * 42,
        "ida_" + "a" * 44,
        "xyz_" + "a" * 43,
        "ida_" + "a" * 42 + "!",
        " ida_" + "a" * 43,
    ],
)
def test_malformed_tokens_are_rejected(value: str) -> None:
    """Wrong prefix, length or characters fail before any lookup."""
    assert not is_well_formed(value)


def test_roles_are_ordered() -> None:
    """An analyst may do everything a viewer may, not the other way round."""
    viewer = Principal(uuid.uuid4(), "v", Role.VIEWER)
    analyst = Principal(uuid.uuid4(), "a", Role.ANALYST)

    assert viewer.allows(Role.VIEWER) and not viewer.allows(Role.ANALYST)
    assert analyst.allows(Role.VIEWER) and analyst.allows(Role.ANALYST)


def test_rate_limiter_uses_a_sliding_window() -> None:
    """Two events per minute; the third waits until the oldest expires."""
    now = [0.0]
    limiter = RateLimiter(lambda: 2, window_seconds=60, clock=lambda: now[0])

    assert limiter.check("token") is None
    now[0] = 10
    assert limiter.check("token") is None
    now[0] = 20
    assert limiter.check("token") == 40
    assert limiter.check("other") is None
    now[0] = 60.5
    assert limiter.check("token") is None


@pytest.mark.real_auth
def test_malformed_token_is_rejected_without_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token of the wrong shape never reaches the database."""

    def no_database() -> Engine:
        raise AssertionError("a malformed token must not open a session")

    monkeypatch.setattr(dependencies, "get_engine", no_database)
    with TestClient(app) as client:
        response = client.get(
            "/api/reports", headers={"Authorization": "Bearer not-a-token"}
        )

    assert response.status_code == 401


@pytest.fixture
def cli_engine(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Engine]:
    """The CLI on the *_test database; issued tokens are removed afterwards."""
    monkeypatch.setattr(cli, "get_engine", lambda: migrated_engine)
    yield migrated_engine
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM api_tokens"))


def test_cli_issues_lists_and_revokes(
    cli_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """The token is printed once; the list shows only its prefix."""
    assert cli.main(["issue", "--name", "Streamlit", "--role", "analyst"]) == 0
    issued = capsys.readouterr().out
    token = next(
        line.split()[1] for line in issued.splitlines() if line.startswith("token:")
    )
    token_id = next(
        line.split()[1] for line in issued.splitlines() if line.startswith("id:")
    )
    assert is_well_formed(token)

    assert cli.main(["list"]) == 0
    listing = capsys.readouterr().out
    assert token[:12] in listing and token not in listing
    assert "active" in listing

    assert cli.main(["revoke", token_id]) == 0
    assert cli.main(["revoke", token_id]) == 1
    assert cli.main(["list"]) == 0
    assert "revoked" in capsys.readouterr().out


def test_cli_rejects_bad_input(
    cli_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """A blank name or a zero expiry is refused with a short message."""
    assert cli.main(["issue", "--name", "  ", "--role", "viewer"]) == 2
    assert cli.main(["issue", "--name", "x", "--role", "viewer", "--days", "0"]) == 2
    assert "Invalid value" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["issue", "--name", "x", "--role", "admin"])
