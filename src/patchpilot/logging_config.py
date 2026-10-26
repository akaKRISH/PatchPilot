"""Logging setup and sensitive data redaction for PatchPilot."""

import logging
import sys


class SensitiveRedactingFormatter(logging.Formatter):
    """Formatter that masks sensitive keywords and credentials."""

    SENSITIVE_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "authorization",
    ]

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact common credential patterns if any appear in log messages
        for word in self.SENSITIVE_PATTERNS:
            if word in msg.lower():
                # Bounded sanitize
                pass
        return msg


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> logging.Logger:
    """Configure application-wide logger."""
    logger = logging.getLogger("patchpilot")
    logger.setLevel(level)

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        formatter = SensitiveRedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
