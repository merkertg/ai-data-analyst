"""Local API connection settings for the Streamlit process."""

from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class UISettings(BaseSettings):
    """Read UI_API_URL and UI_REQUEST_TIMEOUT_SECONDS without exposing secrets."""

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

    @field_validator("api_url")
    @classmethod
    def local_api_url(cls, value: str) -> str:
        """Allow only an HTTP(S) loopback origin without credentials or a path."""
        value = value.strip()
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            raise ValueError("UI_API_URL must be a local HTTP(S) origin") from None
        if (
            parsed.scheme not in {"http", "https"}
            or host not in {"localhost", "127.0.0.1", "::1"}
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
