"""Validate the local-only UI configuration without reading the real .env."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ui.config import UISettings


def test_defaults_are_local_and_allow_the_agent_time_budget() -> None:
    """The default API is loopback and its timeout exceeds the agent's budget."""
    settings = UISettings(_env_file=None)
    assert settings.api_url == "http://127.0.0.1:8000"
    assert settings.request_timeout_seconds == 150


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://localhost:8000/", "http://localhost:8000"),
        ("https://LOCALHOST", "https://localhost"),
        ("http://127.0.0.1:1", "http://127.0.0.1:1"),
        ("https://[::1]:65535/", "https://[::1]:65535"),
        ("http://[::1]", "http://[::1]"),
    ],
)
def test_only_loopback_origins_are_normalized(value: str, expected: str) -> None:
    """Allowed hosts work over HTTP(S), with optional valid ports."""
    assert UISettings(api_url=value, _env_file=None).api_url == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "http://0.0.0.0:8000",
        "http://127.1:8000",
        "http://2130706433:8000",
        "http://localhost.example.com",
        "http://localhost:8000/api",
        "http://localhost:8000//",
        "http://localhost:8000?",
        "http://localhost:8000?token=private",
        "http://localhost:8000#",
        "http://localhost:8000#private",
        "http://private:private@localhost:8000",
        "http://@localhost:8000",
        "http://localhost:0",
        "http://localhost:65536",
        "http://localhost:",
        "http://localhost:not-a-port",
        "http://[::1",
        "http://local\thost:8000",
        "http://localhost:8000/\nprivate",
        "file://localhost",
        "ftp://localhost",
        "localhost:8000",
        "",
    ],
)
def test_external_or_ambiguous_urls_are_rejected(value: str) -> None:
    """Credentials, remote hosts and URL extras cannot reach the HTTP client."""
    with pytest.raises(ValidationError):
        UISettings(api_url=value, _env_file=None)


def test_invalid_secret_url_is_hidden_in_validation_message() -> None:
    """Error text must not copy an invalid URL's embedded credentials."""
    marker = "a-secret-that-must-not-appear"
    with pytest.raises(ValidationError) as caught:
        UISettings(api_url=f"http://user:{marker}@localhost", _env_file=None)
    assert marker not in str(caught.value)


@pytest.mark.parametrize("timeout", [0, 0.9, 600.1, float("inf"), float("nan")])
def test_invalid_timeout_is_rejected(timeout: float) -> None:
    """The client cannot have an unbounded or unusably short timeout."""
    with pytest.raises(ValidationError):
        UISettings(request_timeout_seconds=timeout, _env_file=None)


def test_only_prefixed_environment_variables_are_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI settings do not reuse database/API credentials or unrelated timeouts."""
    monkeypatch.setenv("API_URL", "https://remote.example")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "9999")
    monkeypatch.setenv("UI_API_URL", "http://localhost:8123/")
    monkeypatch.setenv("UI_REQUEST_TIMEOUT_SECONDS", "180")
    settings = UISettings(_env_file=None)
    assert settings.api_url == "http://localhost:8123"
    assert settings.request_timeout_seconds == 180


def test_compose_service_name_must_be_allowed_explicitly() -> None:
    """Stage 10: http://api:8000 works only with UI_ALLOWED_API_HOSTS=api."""
    with pytest.raises(ValidationError):
        UISettings(api_url="http://api:8000", _env_file=None)

    settings = UISettings(
        api_url="http://api:8000", allowed_api_hosts="api", _env_file=None
    )

    assert settings.api_url == "http://api:8000"


@pytest.mark.parametrize(
    "hosts", ["example.com", "10.0.0.5", "2130706433", "api, evil.example", "-api"]
)
def test_only_single_label_names_can_be_allowed(hosts: str) -> None:
    """Domains and IP addresses can never be allowed for the token."""
    with pytest.raises(ValidationError):
        UISettings(allowed_api_hosts=hosts, _env_file=None)


def test_token_is_read_from_a_file(tmp_path: Path) -> None:
    """The bootstrap service writes the token to a file the UI reads."""
    token = "ida_" + "t" * 43
    path = tmp_path / "ui_token"
    path.write_text(token + "\n", encoding="utf-8")

    settings = UISettings(api_token_file=path, _env_file=None)

    assert settings.api_token is not None
    assert settings.api_token.get_secret_value() == token
    assert token not in repr(settings)


def test_missing_token_file_means_no_token(tmp_path: Path) -> None:
    """A file that does not exist yet does not crash the interface."""
    missing = tmp_path / "absent"

    assert UISettings(api_token_file=missing, _env_file=None).api_token is None


def test_explicit_token_wins_over_the_file(tmp_path: Path) -> None:
    """UI_API_TOKEN set directly is used as is."""
    path = tmp_path / "ui_token"
    path.write_text("ida_" + "f" * 43, encoding="utf-8")
    direct = "ida_" + "d" * 43

    settings = UISettings(api_token=direct, api_token_file=path, _env_file=None)

    assert settings.api_token is not None
    assert settings.api_token.get_secret_value() == direct
