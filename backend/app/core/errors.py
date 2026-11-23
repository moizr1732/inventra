"""Application-wide error handling.

Unexpected errors are logged with full detail on the server and returned to
the client as a generic message, so stack traces and SQL never leak out.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger("inventra")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(OperationalError)
    async def database_unavailable(request: Request, exc: OperationalError):
        logger.error("Database unavailable on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "The database is currently unavailable. Please try again shortly."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "A database error occurred. The change was not saved."},
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred."},
        )
