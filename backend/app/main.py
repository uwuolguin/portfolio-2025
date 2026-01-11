"""
Proveo API - Main Application Entry Point

FastAPI application with:
- Database connection pooling
- Redis caching with graceful degradation
- Structured logging with correlation IDs
- Comprehensive error handling
- Security middleware
- Scheduled maintenance jobs
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database.connection import init_db_pools, close_db_pools
from app.redis.redis_client import redis_client
from app.middleware.cors import setup_cors
from app.middleware.logging import LoggingMiddleware, setup_logging
from app.middleware.security import (
    SecurityHeadersMiddleware,
    HTTPSRedirectMiddleware,
)
from app.routers import users, products, communes, companies, health
from app.utils.exceptions import register_exception_handlers

setup_logging()

logger = structlog.get_logger(__name__)


async def scheduled_cleanup():
    """Run orphan image cleanup job"""
    logger.info("scheduled_cleanup_started")
    try:
        from scripts.maintenance.cleanup_orphan_images import cleanup_orphan_images
        await cleanup_orphan_images()
        logger.info("scheduled_cleanup_completed")
    except Exception as e:
        logger.error(
            "scheduled_cleanup_failed",
            error=str(e),
            exc_info=True
        )


def create_app() -> FastAPI:
    """Factory function to create a FastAPI app instance with fresh scheduler"""
    
    scheduler = AsyncIOScheduler()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan context with scheduled jobs"""
        logger.info("application_startup_begin")

        try:
            await init_db_pools()
            logger.info("database_pools_initialized")

            await redis_client.connect()
            logger.info("redis_connected")

            scheduler.add_job(
                scheduled_cleanup,
                CronTrigger(hour="*", minute="*/15"),
                id="cleanup_orphan_images",
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            scheduler.start()
            logger.info(
                "scheduler_started",
                jobs=[
                    {
                        "id": job.id,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                    }
                    for job in scheduler.get_jobs()
                ]
            )

            logger.info("application_startup_complete")

        except Exception as e:
            logger.critical("application_startup_failed", error=str(e), exc_info=True)
            raise

        yield

        logger.info("application_shutdown_begin")

        try:
            scheduler.shutdown(wait=False)
            logger.info("scheduler_stopped")

            await close_db_pools()
            logger.info("database_pools_closed")

            await redis_client.disconnect()
            logger.info("redis_disconnected")

            logger.info("application_shutdown_complete")

        except Exception as e:
            logger.error("application_shutdown_error", error=str(e), exc_info=True)

    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Register custom exception handlers
    register_exception_handlers(app)

    # Add middleware (order matters - first added = last executed)
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    setup_cors(app)
    app.add_middleware(LoggingMiddleware)

    @app.middleware("http")
    async def global_rate_limit_middleware(request: Request, call_next):
        """Apply global rate limiting to API endpoints"""
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        if request.url.path.startswith("/files/"):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            try:
                from app.redis.rate_limit import enforce_rate_limit

                await enforce_rate_limit(
                    request=request,
                    route_name="global",
                    ip_limit=2,
                    global_limit=20,
                    window_seconds=1,
                )
            except Exception as e:
                logger.warning("rate_limit_check_failed", error=str(e))

        return await call_next(request)

    # Include routers
    app.include_router(users.router, prefix=settings.api_v1_prefix)
    app.include_router(products.router, prefix=settings.api_v1_prefix)
    app.include_router(communes.router, prefix=settings.api_v1_prefix)
    app.include_router(companies.router, prefix=settings.api_v1_prefix)
    app.include_router(health.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()