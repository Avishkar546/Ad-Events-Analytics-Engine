"""
Structured logging setup. Kept intentionally minimal in v0.1 — real
job-run metrics logging arrives in v0.7, but every version from here on
should log through this, not print().
"""
import logging
import sys


def configure_logging(environment: str = "local") -> None:
    level = logging.DEBUG if environment == "local" else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
