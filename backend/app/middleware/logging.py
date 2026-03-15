import sys
import asyncio
import time
import logging
import json
import structlog
from datetime import datetime, timezone
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from temporalio.runtime import (
    LogForwardingConfig,
    LoggingConfig,
    Runtime,
    TelemetryConfig,
    TelemetryFilter,
)


def setup_logging() -> None:
    """
    Configure stdlib logging + structlog for the whole process.
    Call this once at startup (e.g. in main.py), before creating loggers.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def install_sync_exception_handler() -> None:
    """
    Install a structured JSON handler for uncaught synchronous exceptions.
    Call once at startup, after setup_logging().
    """
    _log = structlog.get_logger("exception.sync")

    def _sync_excepthook(exc_type, exc_value, exc_traceback):
        _log.critical(
            "sync_uncaught_exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _sync_excepthook


def install_async_exception_handler() -> None:
    """
    Install a structured JSON handler for uncaught asyncio exceptions.
    Must be called from inside a running event loop (e.g. inside run_worker()).
    """
    _log = structlog.get_logger("exception.async")

    def _async_exception_handler(loop, context):
        exc = context.get("exception")
        if exc is not None:
            _log.error(
                "uncaught_async_exception",
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            _log.error(
                "uncaught_async_exception_with_no_exc_object",
                context=str(context),
            )

    try:
        # Already inside a running loop — patch it directly
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_async_exception_handler)
    except RuntimeError:
        # No loop running yet — create one, configure it, register it
        # asyncio.run() will use the loop set via set_event_loop()
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(_async_exception_handler)
        asyncio.set_event_loop(loop)


class _SdkJsonFormatter(logging.Formatter):
    """For temporalio.* Python-side logs — includes timestamp."""
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log)


class _CoreJsonFormatter(logging.Formatter):
    """For Rust core logs — no timestamp, nothing non-deterministic."""
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log)


def configure_temporal_logging() -> None:
    """
    Route all Temporal logs (Python SDK + Rust core) through JSON formatters.
    Must be called before Client.connect() and before any Temporal code runs.
    """
    # ── Python SDK logs ──────────────────────────────────────────────────
    sdk_logger = logging.getLogger("temporalio")
    sdk_logger.setLevel(logging.WARNING)
    sdk_logger.propagate = False
    sdk_handler = logging.StreamHandler(sys.stdout)
    sdk_handler.setFormatter(_SdkJsonFormatter())
    sdk_logger.addHandler(sdk_handler)

    # ── Rust core logs ───────────────────────────────────────────────────
    # Without LogForwardingConfig, Rust core logs bypass Python logging entirely
    # and print raw unformatted text to the console.
    core_logger = logging.getLogger("temporalio.core")
    core_logger.setLevel(logging.WARNING)
    core_logger.propagate = False
    core_handler = logging.StreamHandler(sys.stdout)
    core_handler.setFormatter(_CoreJsonFormatter())
    core_logger.addHandler(core_handler)

    Runtime.set_default(
        Runtime(
            telemetry=TelemetryConfig(
                logging=LoggingConfig(
                    filter=TelemetryFilter(
                        core_level="WARN",
                        other_level="WARN",
                    ),
                    forwarding=LogForwardingConfig(
                        logger=core_logger,
                        append_target_to_name=True,
                    ),
                )
            )
        )
    )


logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Enhanced logging with security-focused information and contextvars.

    All logs within a request automatically include:
    - correlation_id
    - client_ip
    - method
    - path
    - user_id (if authenticated)
    """

    EXCLUDE_PATHS = {"/health", "/favicon.ico", "/"}

    SENSITIVE_HEADERS = {
        "authorization",
        "cookie",
        "x-csrf-token",
        "x-api-key",
        "set-cookie",
    }

    @staticmethod
    def _sanitize_headers(headers: dict) -> dict:
        """
        Redact sensitive headers before logging.

        - Sensitive header names are matched case-insensitively.
        - Values for those headers are replaced with "***REDACTED***".
        """
        sanitized = {}

        for key, value in headers.items():
            key_lower = key.lower()

            if key_lower in LoggingMiddleware.SENSITIVE_HEADERS:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def _is_suspicious_path(path: str) -> bool:
        """Detect common attack patterns in URL paths."""
        suspicious_patterns = [
            "..", "~", "/etc/", "/proc/", "/sys/",
            "eval(", "exec(", "system(", "<script",
            "select", "union", "drop", "insert",
            ".php", ".asp", ".jsp", ".cgi",
            "wp-admin", "wp-login", "phpmyadmin",
            "xmlrpc", ".env", ".git",
        ]

        path_lower = path.lower()
        return any(pattern in path_lower for pattern in suspicious_patterns)

    @staticmethod
    def _extract_user_id(request: Request) -> str | None:
        """
        Extract user_id from JWT cookie if present.
        """
        try:
            token = request.cookies.get("access_token")
            if not token:
                return None

            from app.auth.jwt import decode_access_token
            payload = decode_access_token(token)

            if payload and "sub" in payload:
                return payload["sub"]

            return None
        except Exception:
            return None

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        clear_contextvars()

        correlation_id = request.headers.get(
            "X-Correlation-ID",
            f"req_{int(time.time() * 1000)}",
        )

        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        real_ip = request.headers.get("X-Real-IP", client_ip)
        user_agent = request.headers.get("user-agent", "unknown")

        user_id = self._extract_user_id(request)

        bind_contextvars(
            correlation_id=correlation_id,
            client_ip=client_ip,
            real_ip=real_ip,
            method=request.method,
            path=request.url.path,
            user_id=user_id,
        )

        sanitized_headers = self._sanitize_headers(dict(request.headers))

        start_time = time.time()

        logger.info(
            "request_started",
            query_params=str(request.query_params) if request.query_params else None,
            user_agent=user_agent,
            referer=request.headers.get("referer"),
            content_type=request.headers.get("content-type"),
            headers=sanitized_headers,
        )

        response = await call_next(request)

        duration = time.time() - start_time

        if response.status_code >= 500:
            log_level = "error"
        elif response.status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"

        getattr(logger, log_level)(
            "request_completed",
            status_code=response.status_code,
            duration_ms=f"{duration * 1000:.2f}",
            response_size=response.headers.get("content-length", "unknown"),
            suspicious_path=self._is_suspicious_path(request.url.path),
            unusual_method=request.method
            not in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
            high_duration=duration > 5.0,
        )

        response.headers["X-Correlation-ID"] = correlation_id

        return response