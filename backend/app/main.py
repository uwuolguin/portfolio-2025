from contextlib import asynccontextmanager
import traceback

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

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

"""
Application entrypoint.

This module wires together:
- Startup/shutdown lifecycle using FastAPI lifespan.
- Global logging configuration via structlog.
- Two different middleware "worlds":
    1) Starlette/class-based middleware registered with app.add_middleware(...)
    2) FastAPI/function-based middleware registered with @app.middleware("http")
- Exception handlers for HTTP 413 and 500.
- Routers for the main API endpoints.

Execution order summary for a typical /api/... request:

1. Starlette/class-based middleware ("World 1") in reverse add order:
   - LoggingMiddleware
   - CORSMiddleware (inserted by setup_cors)
   - SecurityHeadersMiddleware
   - HTTPSRedirectMiddleware

2. FastAPI/function-based middleware ("World 2") in declaration order:
   - global_exception_handler
   - global_rate_limit_middleware

3. The actual route handler.

Response bubbles back in the exact reverse order of the above.

This means, for /api/...:
- LoggingMiddleware is the first piece of code to see the request and the last
  piece to see the response, which is ideal for request/response logging.
- Redis-based rate limiting is enforced immediately before the route handler.
- global_exception_handler acts as a safety net around all route logic and
  function-based middlewares, converting unexpected uncaught exceptions into
  a structured 500 JSON response with logging.
"""

setup_logging()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context.

    This is executed once when the application starts and once when it shuts down.

    On startup:
    - Logs "application_startup_begin".
    - Initializes database connection pools via init_db_pools.
    - Connects to Redis using redis_client.connect.
    - Logs completion events if successful.
    - If anything fails, logs a critical error and re-raises, preventing startup.

    On shutdown:
    - Logs "application_shutdown_begin".
    - Closes database pools via close_db_pools.
    - Disconnects Redis using redis_client.disconnect.
    - Logs completion events.
    - Logs any errors that occur during shutdown but does not re-raise them.
    """
    logger.info("application_startup_begin")

    try:
        await init_db_pools()
        logger.info("database_pools_initialized")

        await redis_client.connect()
        logger.info("application_startup_complete")

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



"""
"World 1": Starlette / class-based middleware stack.

These middlewares are registered with app.add_middleware(...) and are part of
Starlette's middleware system. Starlette applies them in reverse order of
registration.

If middleware A is added before middleware B:

    app.add_middleware(A)
    app.add_middleware(B)

then for an incoming request the order is:

    B → A → FastAPI core (function middlewares + routes)

and the response goes back as:

    route → A → B → client

In this application, the class-based middleware registration order is:

    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    setup_cors(app)  # internally adds CORSMiddleware
    app.add_middleware(LoggingMiddleware)

Therefore, the request chain for class-based middleware is:

    LoggingMiddleware
    → CORSMiddleware
    → SecurityHeadersMiddleware
    → HTTPSRedirectMiddleware
    → FastAPI core

and the response chain is the reverse.

This guarantees that:
- LoggingMiddleware sees all requests first and modifies the response last.
- CORS and security headers are applied to requests and responses.
- HTTPSRedirectMiddleware can redirect HTTP requests early in the chain.
"""


app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
setup_cors(app)
app.add_middleware(LoggingMiddleware)


"""
"World 2": FastAPI / function-based middleware stack.

These middlewares are registered using the @app.middleware("http") decorator.
FastAPI applies them in the order they are defined in the source code.

If middleware A is defined before middleware B:

    @app.middleware("http")
    async def A(request, call_next): ...

    @app.middleware("http")
    async def B(request, call_next): ...

then for an incoming request the order is:

    A → B → route handler

and the response goes back as:

    route handler → B → A → client

In this application, the function-based middlewares are:

    global_exception_handler  (defined first)
    global_rate_limit_middleware  (defined second)

So, for the function-based layer, the request chain is:

    global_exception_handler → global_rate_limit_middleware → endpoint

and the response chain is:

    endpoint → global_rate_limit_middleware → global_exception_handler
"""


@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Unexpected internal server error"},
        )
@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
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

@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "detail": f"Request body too large. Maximum size: {settings.max_file_size / 1_000_000}MB"
        },
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
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
"""
Combined execution order of both middleware worlds.

For a typical /api/... request that is not excluded by the rate limiter:

REQUEST PATH:

1) Starlette/class-based middleware ("World 1"), in reverse add order:
    - LoggingMiddleware
    - CORSMiddleware (added by setup_cors)
    - SecurityHeadersMiddleware
    - HTTPSRedirectMiddleware

2) FastAPI/function-based middleware ("World 2"), in definition order:
    - global_exception_handler
    - global_rate_limit_middleware

3) The route handler (endpoint).

RESPONSE PATH:

- Route handler returns
- global_rate_limit_middleware returns
- global_exception_handler returns
- HTTPSRedirectMiddleware returns
- SecurityHeadersMiddleware returns
- CORSMiddleware returns
- LoggingMiddleware returns response to the client

Key points:
- LoggingMiddleware is the very first and very last component around the
    entire request, which is ideal for structured request/response logging
    and correlation IDs.
- Rate limiting is applied just before the route logic for /api/... paths.
- global_exception_handler provides a safety net for unhandled Exceptions
    in the function-based layer and the route handlers.
- Exception handlers for HTTP 413 and 500 are not middlewares; they are
    invoked when corresponding HTTPException instances are raised, and they
    still integrate with the logging and middleware flow because the final
    response status is visible to LoggingMiddleware for the
    request_completed log.
"""

app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(products.router, prefix=settings.api_v1_prefix)
app.include_router(communes.router, prefix=settings.api_v1_prefix)
app.include_router(companies.router, prefix=settings.api_v1_prefix)
app.include_router(health.router, prefix=settings.api_v1_prefix)