"""Structured JSON logging + scoped MAF warning suppression (Principle V)."""

from __future__ import annotations

import logging
import os
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

    # Route structlog through the stdlib logging pipeline instead of writing
    # straight to stdout via PrintLoggerFactory. Emitting real LogRecords lets
    # handlers attached to the root logger receive every structlog event -- in
    # particular the Azure Monitor handler installed by configure_azure_monitor()
    # below, so app events land in the Application Insights `traces` table.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Preserve the existing JSON-to-stdout behaviour (terminal + App Service
    # log stream). The handler renders the wrapped event dict back to JSON.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    _configure_azure_monitor()


def _configure_azure_monitor() -> None:
    """Enable Azure Monitor / Application Insights when configured.

    Reads APPLICATIONINSIGHTS_CONNECTION_STRING from the environment (set as an
    App Service application setting in production). When it is absent -- e.g.
    local dev -- this is a no-op, so terminal logging is unchanged. The distro
    auto-instruments FastAPI requests, outbound httpx calls (dependencies) and
    exceptions, and attaches a logging handler to the root logger so structlog
    events flow into the App Insights `traces` table.
    """
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        # Distro not installed in this environment; skip silently.
        return
    configure_azure_monitor(connection_string=connection_string)

    # The distro auto-instruments FastAPI/requests/urllib but NOT httpx, which
    # is what this app uses for outbound calls (OpenAI/Brave/Clerk). Enable it
    # explicitly so those show up as App Insights dependencies.
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except ImportError:
        return
    HTTPXClientInstrumentor().instrument()


def get_logger(name: str = "momdiary") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger().bind(logger=name)
