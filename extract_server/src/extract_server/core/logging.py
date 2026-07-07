from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, level: str | None = None, log_format: str | None = None) -> None:
    """Configure root and uvicorn loggers for stdout (launchd captures this)."""
    resolved_level = (level or os.environ.get("GROCERY_LOG_LEVEL", "INFO")).upper()
    resolved_format = (log_format or os.environ.get("GROCERY_LOG_FORMAT", "text")).lower()

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if resolved_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    root.addHandler(handler)
    root.setLevel(resolved_level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(resolved_level)


def configure_cli_logging(*, verbose: bool = False) -> None:
    """Enable logging for CLI scripts when --verbose is passed."""
    configure_logging(level="DEBUG" if verbose else "INFO")
