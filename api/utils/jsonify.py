from collections.abc import Mapping
from typing import Any

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

OK = 100
NOT_IMPLEMENTED = 101
INVALID_SCHEMA = 102
DATABASE_ERROR = 103
NOT_FOUND = 104
ALREADY_EXISTS = 105
UNSUPPORTED_PROBE = 106
MONITORING_ERROR = 107
FORBIDDEN_TARGET = 108
INTERNAL_ERROR = 109

MESSAGE_CODES: dict[int, str] = {
    OK: "OK",
    NOT_IMPLEMENTED: "Method is not implemented",
    INVALID_SCHEMA: "Invalid schema",
    DATABASE_ERROR: "Database error",
    NOT_FOUND: "Resource not found",
    ALREADY_EXISTS: "Resource already exists",
    UNSUPPORTED_PROBE: "Unsupported probe type",
    MONITORING_ERROR: "Monitoring failure",
    FORBIDDEN_TARGET: "Target address is not allowed",
    INTERNAL_ERROR: "Internal error",
}

# HTTP status used when the caller does not pass one explicitly.
HTTP_STATUS_CODES: dict[int, int] = {
    OK: status.HTTP_200_OK,
    NOT_IMPLEMENTED: status.HTTP_501_NOT_IMPLEMENTED,
    INVALID_SCHEMA: 422,
    DATABASE_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    UNSUPPORTED_PROBE: status.HTTP_400_BAD_REQUEST,
    MONITORING_ERROR: status.HTTP_502_BAD_GATEWAY,
    FORBIDDEN_TARGET: status.HTTP_403_FORBIDDEN,
    INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class Jsonify(JSONResponse):
    """Uniform API envelope.

    Wraps a Pydantic model, a list of them, or any encodable value in::

        {"result": ..., "status": {"code": int, "message": str}, "_metadata": str}

    `code` is an application code from MESSAGE_CODES, independent of the HTTP
    status: pass `http_status` to override the default mapping.
    """

    def __init__(
        self,
        result: Any = None,
        code: int = OK,
        http_status: int | None = None,
        message: str | None = None,
        metadata: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if message is None:
            message = MESSAGE_CODES.get(code, MESSAGE_CODES[INTERNAL_ERROR])
        content = {
            "result": jsonable_encoder(result),
            "status": {"code": code, "message": message},
            "_metadata": metadata,
        }
        super().__init__(
            content=content,
            status_code=http_status or HTTP_STATUS_CODES.get(code, status.HTTP_200_OK),
            headers=headers,
        )


jsonify = Jsonify
