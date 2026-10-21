"""Turn database failures into safe HTTP answers without internal details."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

from app.db.session import DatabaseNotConfigured

# One text for every cause: the database address and driver errors stay private.
NOT_READY = "Database is not ready"

# Documented in OpenAPI for every route that needs the database.
DATABASE_RESPONSES: dict[int | str, dict[str, object]] = {
    503: {"description": "Database not configured or unreachable"},
}


def _not_ready(_: Request, __: Exception) -> JSONResponse:
    """503: the request may succeed later, once the database is available."""
    return JSONResponse(status_code=503, content={"detail": NOT_READY})


def register_error_handlers(app: FastAPI) -> None:
    """Map a missing DATABASE_URL and lost connections to 503.

    Other unexpected errors keep FastAPI's default 500 without a traceback in
    the response. Validation problems are 422 before the database is touched.
    """
    app.add_exception_handler(DatabaseNotConfigured, _not_ready)
    app.add_exception_handler(OperationalError, _not_ready)
    app.add_exception_handler(InterfaceError, _not_ready)
