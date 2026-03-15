"""
mREIT Monitor — FastAPI Application

Main entry point. Sets up:
- FastAPI app with lifespan context manager
- APScheduler for daily polling
- API routes for health checks and manual triggers
- Logging configuration
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mreit-monitor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle:
    - Start APScheduler on startup
    - Shut down scheduler on shutdown
    """
    # Import here to avoid circular imports
    from src.services.scheduler import start_scheduler, shutdown_scheduler

    logger.info("Starting mREIT Monitor...")
    scheduler = start_scheduler()
    logger.info("Scheduler started. Daily poll at %d:%02d %s", settings.poll_hour, settings.poll_minute, settings.poll_timezone)

    yield

    logger.info("Shutting down mREIT Monitor...")
    shutdown_scheduler(scheduler)
    logger.info("Shutdown complete.")


app = FastAPI(
    title="mREIT Monitor",
    description="Automated mREIT financial filing monitor, extractor, and analyzer",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Routes
# ============================================================================

# Import and include API routes
from src.api.routes import router  # noqa: E402
from src.api.review_app import review_router  # noqa: E402
from src.api.frontend_routes import api_router  # noqa: E402

app.include_router(router)
app.include_router(review_router)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.environment == "development",
    )
