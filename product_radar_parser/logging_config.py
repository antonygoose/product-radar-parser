from __future__ import annotations

import logging
from pathlib import Path


SENSITIVE_WORDS = ("authorization", "cookie", "set-cookie", "token", "access_token", "session", "auth", "code")


def redact(value: object) -> str:
    text = str(value)
    lowered = text.lower()
    if any(word in lowered for word in SENSITIVE_WORDS):
        return "[REDACTED]"
    return text


def configure_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("product_radar_parser")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_dir / "parser.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
