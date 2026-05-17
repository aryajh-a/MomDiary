"""Structured JSON logging + scoped MAF warning suppression (Principle V)."""

from __future__ import annotations

import logging
import sys
import warnings

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog + stdlib logging once at application startup."""
    # Principle V: suppress warnings ONLY from agent_framework modules.
    warnings.filterwarnings("ignore", module=r"agent_framework.*")
    warnings.filterwarnings("ignore", module=r"agent_framework_azure_ai.*")

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.setLevel(level)


def get_logger(name: str = "momdiary") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger().bind(logger=name)
