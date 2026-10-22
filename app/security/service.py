"""Issue, list, revoke and check API tokens in PostgreSQL."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ApiToken
from app.security.tokens import (
    Principal,
    Role,
    display_prefix,
    is_well_formed,
    new_token,
    token_hash,
)


def issue_token(
    session: Session, name: str, role: Role, expires_in_days: int | None = None
) -> tuple[ApiToken, str]:
    """Add a token row and return it with the plain token, shown only once.

    The caller commits. Only the hash and a short prefix are stored.
    """
    name = name.strip()
    if not name:
        raise ValueError("token name must not be blank")
    if expires_in_days is not None and expires_in_days < 1:
        raise ValueError("expiry must be at least one day")
    token = new_token()
    expires_at = (
        None
        if expires_in_days is None
        else datetime.now(UTC) + timedelta(days=expires_in_days)
    )
    row = ApiToken(
        name=name,
        role=role.value,
        token_hash=token_hash(token),
        prefix=display_prefix(token),
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return row, token


def list_tokens(session: Session) -> list[ApiToken]:
    """All tokens, newest first; hashes stay in the database."""
    return list(
        session.scalars(
            select(ApiToken).order_by(ApiToken.created_at.desc(), ApiToken.id)
        )
    )


def revoke_token(session: Session, token_id: uuid.UUID) -> bool:
    """Mark a token revoked; False if it does not exist or was revoked already."""
    row = session.get(ApiToken, token_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    session.flush()
    return True


def authenticate(
    session: Session, token: str, now: datetime | None = None
) -> Principal | None:
    """The caller behind a valid token, or None for any kind of bad token.

    Missing, malformed, unknown, revoked and expired tokens all give None:
    the API answers them the same way, so a client cannot tell them apart.
    """
    if not is_well_formed(token):
        return None
    moment = now or datetime.now(UTC)
    row = session.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == token_hash(token),
            ApiToken.revoked_at.is_(None),
            or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > moment),
        )
    )
    if row is None:
        return None
    return Principal(token_id=row.id, name=row.name, role=Role(row.role))
