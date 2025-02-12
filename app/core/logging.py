"""Logging configuration for the facial recognition service."""
import logging
import sys
from typing import Any, Dict

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True)
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name.
    
    Args:
        name: Name for the logger, typically __name__
        
    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    return structlog.get_logger(name) 