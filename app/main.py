"""Main application module for the facial recognition service."""
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_v1_router
from app.core.config import settings
from app.core.container import container

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    """Handle application startup and shutdown events.

    Args:
        app: FastAPI application instance

    Returns:
        AsyncGenerator[Any, None]: Async context manager for app lifecycle
    """
    # Startup tasks
    logger.info(
        "Starting up facial recognition service",
        extra={
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }
    )

    # Initialize services
    await container.initialize(app)
    logger.info("Initialized application services")

    yield

    # Shutdown tasks
    logger.info("Shutting down facial recognition service")
    await container.cleanup()
    logger.info("Cleaned up application resources")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint.

    Returns:
        dict: Health status
    """
    logger.info("Health check requested")
    return {"status": "healthy"}
