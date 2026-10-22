"""Who may call /api/*: bearer tokens, roles and per-token rate limits.

Every /api route needs `Authorization: Bearer <token>`. /health, /ready and
the documentation pages stay open: they reveal no business data. A missing,
malformed, unknown, revoked or expired token gets the same 401, so a client
cannot learn which tokens exist. The token itself is never stored, logged or
returned; only its SHA-256 is compared with the database.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import LazySession
from app.api.rate_limit import RateLimiter
from app.config import get_settings
from app.security.service import authenticate
from app.security.tokens import Principal, Role, is_well_formed

NOT_AUTHENTICATED = "A valid API token is required (Authorization: Bearer <token>)."
FORBIDDEN = "This action requires the analyst role."
TOO_MANY = "Too many requests for this token; try again later."

# auto_error=False: this module builds the 401 itself, always as JSON.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="ApiToken",
    description="An API token issued with `python -m app.security issue`.",
)

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"description": "Missing, invalid, revoked or expired API token"},
}
WRITE_RESPONSES: dict[int | str, dict[str, object]] = {
    403: {"description": "The token's role does not allow this action"},
    429: {"description": "Rate limit for this token exceeded; see Retry-After"},
}

agent_limiter = RateLimiter(lambda: get_settings().agent_runs_per_minute)
report_limiter = RateLimiter(lambda: get_settings().reports_per_minute)


def _unauthorized() -> HTTPException:
    """One answer for every kind of bad token."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=NOT_AUTHENTICATED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """Check the token before the route runs.

    A missing or malformed token is rejected without SQL. A well-formed token
    is looked up in its own short read-only session, separate from the
    route's session. FastAPI caches the result within one request.
    """
    if credentials is None or not is_well_formed(credentials.credentials):
        raise _unauthorized()
    with LazySession(read_only=True) as session:
        principal = authenticate(session, credentials.credentials)
    if principal is None:
        raise _unauthorized()
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_analyst(principal: CurrentPrincipal) -> Principal:
    """Writes and agent runs are for analysts; viewers only read."""
    if not principal.allows(Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN)
    return principal


def _limited(limiter: RateLimiter, principal: Principal) -> None:
    """Raise 429 with Retry-After when the token is over its limit."""
    wait = limiter.check(principal.token_id)
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_MANY,
            headers={"Retry-After": str(wait)},
        )


def limit_agent_runs(
    principal: Annotated[Principal, Depends(require_analyst)],
) -> None:
    """At most AGENT_RUNS_PER_MINUTE agent runs per token."""
    _limited(agent_limiter, principal)


def limit_reports(principal: Annotated[Principal, Depends(require_analyst)]) -> None:
    """At most REPORTS_PER_MINUTE saved reports per token."""
    _limited(report_limiter, principal)
