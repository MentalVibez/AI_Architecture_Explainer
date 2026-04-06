"""Configure structured JSON logging for non-development environments.

In development the default uvicorn text formatter is left untouched.
In staging/production every log record is emitted as a single JSON line
so Railway / any log aggregator can index fields directly.
"""
import json
import logging
import traceback


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = traceback.format_exception(*record.exc_info)
        # Forward any extra fields attached by callers (e.g. job_id=...)
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str)


def configure_logging(environment: str) -> None:
    """Call once at process startup (after settings are loaded)."""
    if environment == "development":
        return

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
