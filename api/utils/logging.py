import json
import logging
from datetime import UTC, datetime

# Attributes LogRecord always carries; anything else was passed via extra= and
# belongs in the structured output.
_RESERVED = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
    | {"asctime", "message", "taskName"}
)

# Never let a secret reach the log stream, however it was passed in.
_REDACTED_KEYS = frozenset({"password", "token", "secret", "authorization", "api_key"})


class JSONFormatter(logging.Formatter):
    """Render records as one JSON object per line, keeping extra= context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED:
                continue
            payload[key] = "***" if key.lower() in _REDACTED_KEYS else value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", structured: bool = True) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JSONFormatter()
        if structured
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
