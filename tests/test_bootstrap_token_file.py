"""Bootstrap token-file protection with fake credentials and no database access."""

import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app import bootstrap
from app.security.tokens import Principal, Role

CURRENT_TOKEN = "test-only-existing-token"
ISSUED_TOKEN = "test-only-issued-token"


@pytest.fixture
def token_services(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Replace credential SQL with explicit mocks; no test can open a database."""
    authenticate = MagicMock(return_value=None)
    issue = MagicMock(return_value=(None, ISSUED_TOKEN))
    revoke = MagicMock()
    monkeypatch.setattr(bootstrap, "authenticate", authenticate)
    monkeypatch.setattr(bootstrap, "issue_token", issue)
    monkeypatch.setattr(bootstrap, "revoke_token", revoke)
    return authenticate, issue, revoke


@pytest.fixture
def session() -> MagicMock:
    """A session whose token-list query has no existing demo tokens."""
    result = MagicMock(spec=Session)
    result.scalars.return_value = []
    return result


def principal(role: Role) -> Principal:
    """A non-secret fake identity with the requested permission level."""
    return Principal(uuid.UUID(int=1), "fake bootstrap identity", role)


def test_valid_private_analyst_file_is_kept_without_rewriting(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """A correctly protected analyst file keeps its bytes and inode."""
    authenticate, issue, _ = token_services
    authenticate.return_value = principal(Role.ANALYST)
    path = tmp_path / "ui_token"
    path.write_text(CURRENT_TOKEN + "\n", encoding="utf-8")
    path.chmod(0o600)
    original_inode = path.stat().st_ino

    assert bootstrap.ensure_ui_token(session, path) == "kept"

    assert path.read_text(encoding="utf-8") == CURRENT_TOKEN + "\n"
    assert path.stat().st_ino == original_inode
    issue.assert_not_called()
    session.scalars.assert_not_called()


def test_viewer_file_is_replaced_with_an_analyst_token(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """A working viewer cannot satisfy the interface's write permissions."""
    authenticate, issue, _ = token_services
    authenticate.return_value = principal(Role.VIEWER)
    path = tmp_path / "ui_token"
    path.write_text(CURRENT_TOKEN, encoding="utf-8")

    assert bootstrap.ensure_ui_token(session, path) == "issued"

    issue.assert_called_once_with(session, bootstrap.UI_TOKEN_NAME, Role.ANALYST)
    assert path.read_text(encoding="utf-8") == ISSUED_TOKEN + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_stale_permissive_temporary_file_is_untouched(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """A pre-existing fixed .tmp name cannot donate its unsafe permissions."""
    path = tmp_path / "ui_token"
    stale = path.with_name(path.name + ".tmp")
    stale.write_text("unrelated stale contents", encoding="utf-8")
    stale.chmod(0o644)

    assert bootstrap.ensure_ui_token(session, path) == "issued"

    assert path.read_text(encoding="utf-8") == ISSUED_TOKEN + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stale.read_text(encoding="utf-8") == "unrelated stale contents"
    assert stat.S_IMODE(stale.stat().st_mode) == 0o644
    assert set(tmp_path.iterdir()) == {path, stale}


def test_stale_temporary_symlink_does_not_modify_its_target(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """The old predictable .tmp path is never opened or followed."""
    path = tmp_path / "ui_token"
    target = tmp_path / "unrelated"
    target.write_text("original unrelated contents", encoding="utf-8")
    stale = path.with_name(path.name + ".tmp")
    stale.symlink_to(target)

    assert bootstrap.ensure_ui_token(session, path) == "issued"

    assert stale.is_symlink()
    assert target.read_text(encoding="utf-8") == "original unrelated contents"
    assert path.read_text(encoding="utf-8") == ISSUED_TOKEN + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_permissive_analyst_file_is_repaired_without_rotating_token(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Atomic replacement protects an existing analyst credential in place."""
    authenticate, issue, _ = token_services
    authenticate.return_value = principal(Role.ANALYST)
    path = tmp_path / "ui_token"
    path.write_text(CURRENT_TOKEN, encoding="utf-8")
    path.chmod(0o644)

    assert bootstrap.ensure_ui_token(session, path) == "kept"

    assert path.read_text(encoding="utf-8") == CURRENT_TOKEN + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    issue.assert_not_called()


def test_analyst_destination_symlink_is_replaced_without_chmod_of_target(
    tmp_path: Path,
    session: MagicMock,
    token_services: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """A kept token becomes a private regular file; its old target is intact."""
    authenticate, issue, _ = token_services
    authenticate.return_value = principal(Role.ANALYST)
    target = tmp_path / "external-token"
    target.write_text(CURRENT_TOKEN, encoding="utf-8")
    target.chmod(0o644)
    path = tmp_path / "ui_token"
    path.symlink_to(target)

    assert bootstrap.ensure_ui_token(session, path) == "kept"

    assert not path.is_symlink()
    assert path.read_text(encoding="utf-8") == CURRENT_TOKEN + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert target.read_text(encoding="utf-8") == CURRENT_TOKEN
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    issue.assert_not_called()


@pytest.mark.parametrize("failure", ["write", "replace"])
def test_failed_atomic_install_cleans_temporary_and_keeps_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """A partial write or failed rename leaves no extra credential copy."""
    path = tmp_path / "ui_token"
    path.write_text(CURRENT_TOKEN, encoding="utf-8")
    original_fdopen = os.fdopen

    @contextmanager
    def failing_write(
        descriptor: int, *args: Any, **kwargs: Any
    ) -> Iterator[MagicMock]:
        """Write a fragment before simulating a failed file write."""
        with original_fdopen(descriptor, *args, **kwargs) as stream:
            wrapper = MagicMock(wraps=stream)

            def write_fragment(value: str) -> None:
                """Leave a partial secret only in the temporary file."""
                stream.write(value[:4])
                raise OSError("simulated write failure")

            wrapper.write.side_effect = write_fragment
            yield wrapper

    def failing_replace(source: Path, destination: Path) -> Path:
        """Refuse the final rename after the private file was written."""
        assert destination == path
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        raise OSError("simulated replace failure")

    if failure == "write":
        monkeypatch.setattr(os, "fdopen", failing_write)
    else:
        monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError, match=f"simulated {failure} failure"):
        bootstrap._write_token_file(path, ISSUED_TOKEN)

    assert path.read_text(encoding="utf-8") == CURRENT_TOKEN
    assert set(tmp_path.iterdir()) == {path}
