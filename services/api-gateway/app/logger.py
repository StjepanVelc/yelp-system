import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.observability import get_correlation_id

_DEFAULT_LOG_DIR = Path("/logs")
_LOG_DIR = _DEFAULT_LOG_DIR if _DEFAULT_LOG_DIR.exists() else Path(__file__).resolve().parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        extras = {
            "method",
            "path",
            "status_code",
            "latency_ms",
            "service",
        }
        for key in extras:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    formatter = JsonFormatter()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Rotating file handler — 10 MB per file, 5 backups
    service_name = name.split(".")[0]
    file_handler = RotatingFileHandler(
        _LOG_DIR / f"{service_name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
