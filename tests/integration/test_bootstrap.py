"""Stand bootstrap on the *_test database: demo data once, a working UI token."""

import stat
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import bootstrap
from app.db.models import ApiToken, Order
from app.db.sample import add_sample_data
from app.security.service import authenticate, revoke_token
from app.security.tokens import token_hash


def test_demo_data_loads_once(db_session: Session) -> None:
    """An empty database gets the seed 42 bundle; a second run changes nothing."""
    loaded = bootstrap.ensure_demo_data(db_session)

    assert loaded is not None and loaded["orders"] == 20_000
    assert bootstrap.ensure_demo_data(db_session) is None
    assert db_session.scalar(select(func.count()).select_from(Order)) == 20_000


def test_existing_data_is_never_touched(db_session: Session) -> None:
    """A database with any customers is left as it is."""
    add_sample_data(db_session)

    assert bootstrap.ensure_demo_data(db_session) is None
    assert db_session.scalar(select(func.count()).select_from(Order)) == 5


def test_ui_token_is_issued_kept_and_replaced(
    db_session: Session, tmp_path: Path
) -> None:
    """Issued once, kept while valid, replaced after revocation."""
    path = tmp_path / "secrets" / "ui_token"

    assert bootstrap.ensure_ui_token(db_session, path) == "issued"
    first = path.read_text(encoding="utf-8").strip()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    principal = authenticate(db_session, first)
    assert principal is not None and principal.role == "analyst"

    assert bootstrap.ensure_ui_token(db_session, path) == "kept"
    assert path.read_text(encoding="utf-8").strip() == first

    assert revoke_token(db_session, principal.token_id)
    assert bootstrap.ensure_ui_token(db_session, path) == "issued"
    second = path.read_text(encoding="utf-8").strip()
    assert second != first and authenticate(db_session, second) is not None


def test_a_garbage_token_file_is_replaced_and_old_tokens_revoked(
    db_session: Session, tmp_path: Path
) -> None:
    """Only one interface token stays active after a replacement."""
    path = tmp_path / "ui_token"
    bootstrap.ensure_ui_token(db_session, path)
    first = path.read_text(encoding="utf-8").strip()
    path.write_text("not-a-token\n", encoding="utf-8")

    assert bootstrap.ensure_ui_token(db_session, path) == "issued"

    active = db_session.scalars(
        select(ApiToken).where(
            ApiToken.name == bootstrap.UI_TOKEN_NAME, ApiToken.revoked_at.is_(None)
        )
    ).all()
    assert len(active) == 1
    assert active[0].token_hash != token_hash(first)


def test_bootstrap_refuses_an_outdated_schema(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without the latest migration nothing is loaded and the exit code is 1."""
    monkeypatch.setattr(bootstrap, "get_engine", lambda: object())
    monkeypatch.setattr(bootstrap, "current_revision", lambda _: "0003")

    assert bootstrap.main(["--no-data"]) == 1
    assert "apply migrations first" in capsys.readouterr().err
