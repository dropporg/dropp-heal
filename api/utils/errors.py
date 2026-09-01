import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from api.utils.jsonify import (
    INTERNAL_ERROR,
    INVALID_SCHEMA,
    MESSAGE_CODES,
    NOT_FOUND,
    Jsonify,
)

logger = logging.getLogger("heal.errors")

# HTTP statuses that map onto a more specific application code.
_STATUS_CODES = {404: NOT_FOUND, 422: INVALID_SCHEMA}


def register_error_handlers(app: FastAPI) -> None:
    """Return every error in the same envelope as successful responses."""

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        request: Request, exc: RequestValidationError
    ) -> Jsonify:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
            for error in exc.errors()
        )
        return Jsonify(code=INVALID_SCHEMA, metadata=detail)

    @app.exception_handler(HTTPException)
    async def on_http_error(request: Request, exc: HTTPException) -> Jsonify:
        code = _STATUS_CODES.get(exc.status_code, INTERNAL_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else MESSAGE_CODES[code]
        return Jsonify(code=code, http_status=exc.status_code, message=message)

    @app.exception_handler(Exception)
    async def on_unhandled_error(request: Request, exc: Exception) -> Jsonify:
        logger.exception("unhandled error", extra={"path": request.url.path})
        return Jsonify(code=INTERNAL_ERROR)
