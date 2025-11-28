import sys
import time
import logging
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


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
