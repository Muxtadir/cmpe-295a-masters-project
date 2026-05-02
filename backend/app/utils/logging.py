import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structured-ish logging for API and agents."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(level)


class StructuredFormatter(logging.Formatter):
    """JSON lines for easy ingestion by CloudWatch / ELK."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload["extra"] = extra
        return json.dumps(payload, default=str)


def log_structured(
    logger: logging.Logger,
    level: int,
    message: str,
    **fields: Any,
) -> None:
    """Attach a `structured` dict to the LogRecord for StructuredFormatter."""
    logger.log(level, message, extra={"structured": fields})
