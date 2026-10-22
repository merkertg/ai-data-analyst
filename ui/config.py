"""API connection settings for the Streamlit process."""

import re
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
# A single DNS label with at least one letter, such as the Compose service
# "api". Dotted names and numeric hosts can never be allowed: the token must
# not leave the machine or the container network.
_SERVICE_NAME = re.compile(r"(?=[a-z0-9-]*[a-z])[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class UISettings(BaseSettings):
    """Read the API origin, token and timeout without exposing secrets."""

    model_config = SettingsConfigDict(
        env_prefix="UI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    api_url: str = Field(default="http://127.0.0.1:8000", repr=False)
    request_timeout_seconds: float = Field(
        default=150, ge=1, le=600, allow_inf_nan=False
    )
    # Stage 09: the API requires a token. An analyst token lets the interface
    # also save reports and ask the agent; a viewer token only reads.
    api_token: SecretStr | None = Field(default=None, repr=False)
    # Stage 10: Docker Compose passes the token as a file written by the
    # bootstrap service; it is read when settings are created.
    api_token_file: Path | None = Field(default=None, repr=False)
    # Stage 10: extra API hosts besides loopback, such as the Compose service
    # name "api"; comma-separated single-label names only.
    allowed_api_hosts: str = ""

    @field_validator("allowed_api_hosts")
    @classmethod
    def single_label_hosts(cls, value: str) -> str:
        """Accept only container-style names, never domains or IP addresses."""
        names = [name.strip().lower() for name in value.split(",") if name.strip()]
        if not all(_SERVICE_NAME.fullmatch(name) for name in names):
            raise ValueError("UI_ALLOWED_API_HOSTS takes single-label names only")
        return ",".join(names)

    @field_validator("api_token", mode="before")
    @classmethod
    def blank_token_is_missing(cls, value: object) -> object:
        """Treat an empty UI_API_TOKEN as not configured."""
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("api_url")
    @classmethod
    def local_api_url(cls, value: str) -> str:
        """Allow only an HTTP(S) origin without credentials or a path.

        The host must be loopback or a single-label name; whether such a name
        is allowed is checked against UI_ALLOWED_API_HOSTS below.
        """
        value = value.strip()
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            raise ValueError("UI_API_URL must be a local HTTP(S) origin") from None
        if (
            parsed.scheme not in {"http", "https"}
            or host is None
            or not (host in LOOPBACK_HOSTS or _SERVICE_NAME.fullmatch(host))
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or "?" in value
            or "#" in value
            or any(character.isspace() for character in value)
            or parsed.netloc.endswith(":")
            or (port is not None and port < 1)
        ):
            raise ValueError("UI_API_URL must be a local HTTP(S) origin")
        # Rebuild the authority instead of retaining spelling such as host case.
        authority = "[::1]" if host == "::1" else host
        if port is not None:
            authority = f"{authority}:{port}"
        return urlunsplit((parsed.scheme, authority, "", "", ""))

    @model_validator(mode="after")
    def allowed_host_and_token_file(self) -> Self:
        """Check the host against the allow-list, then read a token file."""
        host = urlsplit(self.api_url).hostname
        allowed = LOOPBACK_HOSTS | set(filter(None, self.allowed_api_hosts.split(",")))
        if host not in allowed:
            raise ValueError("UI_API_URL must be a local HTTP(S) origin")
        if self.api_token is None and self.api_token_file is not None:
            try:
                token = self.api_token_file.read_text(encoding="utf-8").strip()
            except OSError:
                # A missing file means "no token": the UI then explains 401.
                token = ""
            self.api_token = SecretStr(token) if token else None
        return self
