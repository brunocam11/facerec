"""Logging configuration for the facial recognition service."""
import logging
import sys
from typing import Any, Dict, List

import structlog
from structlog.stdlib import ProcessorFormatter

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application.
    
    - Uses ConsoleRenderer with colors for development.
    - Uses JSONRenderer for other environments (staging, production).
    - Integrates with standard Python logging handlers.
    """
    shared_processors: List[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name, # Recommended for stdlib integration
        structlog.processors.TimeStamper(fmt="iso", utc=True), # Use UTC timestamps
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter, # Required for stdlib formatter
    ]

    # Configure structlog to work with standard logging
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Determine the final renderer based on environment
    if settings.ENVIRONMENT == "development":
        final_processor = structlog.dev.ConsoleRenderer(colors=True)
        log_format = "%(message)s"
    else:
        # Production/Staging JSON logs
        final_processor = structlog.processors.JSONRenderer()
        # Add exception formatting for JSON logs
        shared_processors.insert(-1, structlog.processors.format_exc_info)
        # Format for stdlib handler (structlog handles the actual rendering)
        log_format = "%(message)s" # structlog ProcessorFormatter handles this

    # Configure the stdlib root logger
    formatter = ProcessorFormatter(
        # These processors run ONLY on entries explicitly passed to stdlib logger
        # via logger.log(), NOT when using logger.info(), logger.error() etc.
        #foreign_pre_chain=shared_processors,
        processor=final_processor,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Clear existing handlers
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)
    # Set log level from settings (convert string like "INFO" to logging constant)
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Configure log levels for dependencies if needed
    logging.getLogger("uvicorn.error").propagate = False # Let root handle uvicorn errors
    logging.getLogger("uvicorn.access").disabled = True # Disable uvicorn access logs if too noisy
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.INFO) # Or WARNING

    # Log confirmation
    root_logger.info(
        f"Logging setup complete. Environment: {settings.ENVIRONMENT}, Level: {settings.LOG_LEVEL}"
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance compatible with standard logging.
    
    Args:
        name: Name for the logger, typically __name__
        
    Returns:
        structlog.stdlib.BoundLogger: Configured logger instance
    """
    return structlog.get_logger(name) 