"""Main application module for the facial recognition service."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import FaceRecognitionError
from app.core.logging import get_logger, setup_logging
from app.infrastructure.api.v1 import router as api_v1_router

# Set up logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
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

@app.exception_handler(FaceRecognitionError)
async def face_rec_exception_handler(request: Request, exc: FaceRecognitionError) -> JSONResponse:
    """Handle FaceRecError exceptions.
    
    Args:
        request: FastAPI request
        exc: FaceRecError instance
        
    Returns:
        JSONResponse: Error response
    """
    logger.error(
        "Request failed",
        error=str(exc),
        status_code=exc.status_code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "details": exc.details},
    )

@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint.
    
    Returns:
        dict: Health status
    """
    logger.info("Health check requested")
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event() -> None:
    """Run startup tasks."""
    logger.info(
        "Starting up facial recognition service",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Run shutdown tasks."""
    logger.info("Shutting down facial recognition service") 