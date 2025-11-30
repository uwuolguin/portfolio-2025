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


class _StarletteMiddlewareDescription:
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


class _FastAPIMiddlewareDescription:
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
    """
    Global HTTP middleware for catching unhandled exceptions.

    This middleware wraps all route handlers and all other function-based
    middlewares that appear after it in the declaration order.

    Behavior:
    - Calls call_next(request) to continue down the chain
      (global_rate_limit_middleware and then the endpoint).
    - If any unhandled Exception bubbles up past call_next, it:
        * Logs the error using structlog, including path, method, and traceback.
        * Returns a JSONResponse with HTTP 500 and a generic error message.

    Role in the combined chain:
    - This middleware is executed after all class-based middlewares
      (Logging, CORS, Security, HTTPS redirect).
    - It is the outermost "safety net" in the function-based layer.
    - It does not handle HTTPException(413) or HTTPException(500) explicitly;
      those are handled by the dedicated exception handlers below.
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Unexpected internal server error"},
        )


@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc):
    """
    Exception handler for HTTP 413 (Request Entity Too Large).

    How it fits into the flow:
    - If any part of the stack (middlewares or route handlers) raises
      HTTPException with status_code 413, FastAPI routes that exception
      to this handler.
    - This handler is not a middleware, it does not change the chain order.
      It is only invoked when a 413 exception is raised.
    - It returns a JSONResponse with status 413 and a message indicating that
      the request body exceeded the configured maximum size (settings.max_file_size).

    Interaction with other middlewares:
    - LoggingMiddleware will still log the request_completed event containing
      status_code 413.
    - global_exception_handler does not see this as an unhandled generic Exception;
      FastAPI handles it directly via this exception handler.
    """
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "detail": f"Request body too large. Maximum size: {settings.max_file_size / 1_000_000}MB"
        },
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """
    Exception handler for HTTP 500 responses raised as HTTPException(500).

    How it fits into the flow:
    - If an HTTPException with status_code 500 is explicitly raised by your
      code (rather than a plain Exception), FastAPI will send it here.
    - This handler logs an "internal_server_error" event with request path,
      method, and the exception details, then returns a JSONResponse with
      a generic 500 error message.

    Relationship with global_exception_handler:
    - global_exception_handler catches generic unhandled Exceptions that are
      not already turned into HTTPException by FastAPI or your own code.
    - This 500 handler is specifically for HTTPException(500) and is invoked
      by FastAPI's own error handling when that type of exception is raised.
    - Both produce a structured JSON 500 response, but through different paths.

    Interaction with the combined middleware chain:
    - Class-based middlewares have already run when this handler is invoked.
    - Function-based middlewares have already been traversed for the request.
    - LoggingMiddleware will still log the final response status (500) in the
      request_completed log entry with the same correlation_id.
    """
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


@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    """
    Global HTTP rate limiting middleware.

    This middleware runs inside the function-based middleware stack and closer
    to the endpoint than global_exception_handler.

    Behavior:
    - Skips rate limiting for the following paths:
        * "/health", "/", "/docs", "/redoc", "/openapi.json"
        * Any path starting with "/files/"
    - For paths starting with "/api/":
        * Imports and calls enforce_rate_limit from app.redis.rate_limit.
        * Enforces per-IP and global request limits within a time window.
        * If Redis is unavailable or rate limit check fails, logs a warning and
          allows the request to proceed (fails open).

    Order within "World 2":
    - REQUEST: global_exception_handler → global_rate_limit_middleware → endpoint
    - RESPONSE: endpoint → global_rate_limit_middleware → global_exception_handler

    Interaction with "World 1":
    - All class-based middlewares (Logging, CORS, Security, HTTPS redirect)
      have already executed before this function is entered.
    - When enforce_rate_limit raises HTTPException(429), FastAPI handles it
      using its standard exception handling and any configured 429
      exception handler (if you add one).

    Overall effect:
    - Ensures that rate limiting logic is applied to API routes just before
      hitting the route logic, while still being wrapped by the global
      exception handler and all class-based middlewares.
    """
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