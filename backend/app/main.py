"""
ContextIQ API — application entry point.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import setup_structured_logging
from app.core.middleware import ObservabilityMiddleware
from app.core.security_middleware import SecurityHardeningMiddleware

logger = logging.getLogger(__name__)

# Initialize structured logging
setup_structured_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Graceful startup and shutdown lifecycle management."""
    logger.info("ContextIQ application starting up. Initializing subsystem connections...")
    yield
    logger.info("ContextIQ application shutting down. Draining worker tasks and releasing connections...")

settings = get_settings()

if settings.APP_ENV == "production" and settings.SECRET_KEY == "dev-secret-change-me":
    raise RuntimeError("SECRET_KEY must be explicitly configured in production.")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "ContextIQ — a privacy-conscious Personal Behaviour Intelligence System. "
        "Learns behavioural patterns around forgetting, context switching, and "
        "recurring 'one more thing' tasks from explicitly-logged user events."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(SecurityHardeningMiddleware)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["root"])
def root():
    return {
        "service": settings.APP_NAME,
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
    }
