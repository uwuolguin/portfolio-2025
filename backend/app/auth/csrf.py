"""
CSRF Protection Module

SECURITY FEATURES:
- Standard CSRF token validation for state-changing requests
- Constant-time comparison to prevent timing attacks
- Comprehensive logging for audit trails
"""

import secrets
from fastapi import Request, HTTPException, status
import structlog

logger = structlog.get_logger(__name__)


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token"""
    return secrets.token_urlsafe(32)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


async def validate_csrf_token(request: Request) -> None:
    """
    Validate CSRF token for state-changing operations.

    Raises:
        HTTPException: If validation fails
    """
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return

    client_ip = _get_client_ip(request)

    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if not cookie_token or not header_token:
        logger.warning(
            "csrf_validation_failed",
            reason="missing_tokens",
            has_cookie=bool(cookie_token),
            has_header=bool(header_token),
            ip=client_ip,
            method=request.method,
            path=request.url.path
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing"
        )

    if not secrets.compare_digest(cookie_token, header_token):
        logger.warning(
            "csrf_validation_failed",
            reason="token_mismatch",
            ip=client_ip,
            method=request.method,
            path=request.url.path
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid"
        )

    logger.debug(
        "csrf_validation_success",
        ip=client_ip,
        method=request.method,
        path=request.url.path
    )