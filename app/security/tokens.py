"""API token format, hashing and roles; no database access here.

A token is shown once when it is issued. The database keeps only its SHA-256
hash: a stolen database copy does not reveal working tokens. Tokens are long
random strings, so a fast hash is enough; slow password hashing exists for
short, guessable human passwords.
"""

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from enum import StrEnum

TOKEN_PREFIX = "ida_"
# token_urlsafe(32) encodes 32 random bytes as 43 URL-safe characters.
_TOKEN = re.compile(r"ida_[A-Za-z0-9_-]{43}")
DISPLAY_LENGTH = 12


class Role(StrEnum):
    """What a token may do: read analytics, or also start costly work."""

    VIEWER = "viewer"
    ANALYST = "analyst"


# A higher level includes every permission of the lower ones.
ROLE_LEVELS = {Role.VIEWER: 1, Role.ANALYST: 2}


@dataclass(frozen=True)
class Principal:
    """The authenticated caller; the token itself is never kept in memory."""

    token_id: uuid.UUID
    name: str
    role: Role

    def allows(self, role: Role) -> bool:
        """True when this caller's role is at least the required one."""
        return ROLE_LEVELS[self.role] >= ROLE_LEVELS[role]


def new_token() -> str:
    """A fresh random token with a recognisable prefix."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def is_well_formed(token: str) -> bool:
    """Reject obviously wrong values before any database lookup."""
    return _TOKEN.fullmatch(token) is not None


def token_hash(token: str) -> str:
    """The SHA-256 hex digest stored instead of the token."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def display_prefix(token: str) -> str:
    """The first characters, enough to recognise a token in a list."""
    return token[:DISPLAY_LENGTH]
