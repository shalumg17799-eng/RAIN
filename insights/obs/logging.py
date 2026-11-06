"""Structured JSON logging: one object per line, never row-like fields, no tracebacks."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from insights.contracts.guards import assert_no_rows


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        line.update(getattr(record, "fields", {}))
        if record.exc_info and record.exc_info[1] is not None:
            line["exc_type"] = type(record.exc_info[1]).__name__
            line["exc_message"] = str(record.exc_info[1])[:300]
        return json.dumps(line, default=str)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log an event with typed fields. Refuses anything that looks like result data."""
    assert_no_rows(fields, f"log event {event!r}")
    logger.log(level, event, extra={"fields": fields})


def configure_logging(level: int = logging.INFO) -> None:
    """Install one JSON handler on the `insights` logger. Safe to call more than once."""
    logger = logging.getLogger("insights")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
