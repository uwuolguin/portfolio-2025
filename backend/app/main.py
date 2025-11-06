from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse
import structlog
import traceback

from app.config import settings
from app.database.connection import init_db_pools, close_db_pools
from app.redis.redis_client import redis_client
from app.redis.rate_limit import get_rate_limiter
from app.middleware.cors import setup_cors
from app.middleware.logging import LoggingMiddleware
from app.middleware.security import (
    SecurityHeadersMiddleware,
    HTTPSRedirectMiddleware,
)
from app.utils.file_handler import FileHandler, NSFWModelError
from app.routers import users, products, communes, companies

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup_begin")

    try:
        FileHandler.init_upload_directory()        
        try:
            FileHandler.load_nsfw_model()
        except NSFWModelError as e:
            logger.critical("nsfw_model_critical_failure", error=str(e))
            logger.warning(
                "starting_without_nsfw_protection",
                message="Images will not be checked for inappropriate content"
            )

        await init_db_pools()
        logger.info("database_pools_initialized")

        await redis_client.connect()
        logger.info("application_startup_complete", nsfw_available=FileHandler._nsfw_available)

    except Exception as e:
        logger.critical("application_startup_failed", error=str(e), exc_info=True)
        raise

    yield

    logger.info("application_shutdown_begin")

    try:
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

@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
    """
    Catches ANY unhandled exception (including those raised inside BaseHTTPMiddleware).
    Ensures consistent JSON error responses and structured logging.
    """
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(e),
            traceback=traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Unexpected internal server error"},
        )


@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc):
    """Handle file upload size limit exceeded"""
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "detail": f"Request body too large. Maximum size: {settings.max_file_size / 1_000_000}MB"
        },
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle unexpected server errors"""
    logger.error(
        "internal_server_error",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error. Please contact support if the issue persists."
        },
    )


app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

setup_cors(app)

app.add_middleware(LoggingMiddleware)

@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    """
    Apply global rate limiting to all API routes
    Skip for health checks and static files
    """
    # Skip rate limiting for these paths
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Skip rate limiting for static files
    if request.url.path.startswith("/files/"):
        return await call_next(request)
    
    # Apply rate limiting to API routes
    if request.url.path.startswith("/api/"):
        try:
            from app.cache.rate_limit import enforce_rate_limit
            await enforce_rate_limit(
                request=request,
                route_name="global",
                ip_limit=2,           # 2 requests per second per IP
                global_limit=20,      # 20 requests per second globally
                window_seconds=1      # 1 second window
            )
        except Exception as e:
            logger.warning("rate_limit_check_failed", error=str(e))
    
    return await call_next(request)


app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(products.router, prefix=settings.api_v1_prefix)
app.include_router(communes.router, prefix=settings.api_v1_prefix)
app.include_router(companies.router, prefix=settings.api_v1_prefix)

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Proveo API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Basic health check"""
    return {
        "status": "healthy",
        "nsfw_checking": FileHandler._nsfw_available,
        "redis_available": redis_client.is_available(),
    }


@app.get("/nsfw-status")
async def nsfw_status():
    """Check NSFW model status (for monitoring/debugging)"""
    return FileHandler.get_nsfw_status()