"""
CSRF Protection Module with Admin Bypass Security

SECURITY FEATURES:
- Standard CSRF token validation for regular users
- Admin bypass with IP whitelist + special rate limiting
- Constant-time comparison to prevent timing attacks
- Comprehensive logging for audit trails

IMPORTANT: Configure ADMIN_BYPASS_IPS in production!
"""

import secrets
import time
from typing import Optional, Set
from fastapi import Request, HTTPException, status
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# In-memory rate limit store for admin bypass attempts
# Format: {ip_address: [(timestamp, success), ...]}
_admin_bypass_attempts: dict[str, list[tuple[float, bool]]] = {}

# Rate limit configuration for admin bypass
ADMIN_BYPASS_RATE_LIMIT_WINDOW = 300  # 5 minutes
ADMIN_BYPASS_MAX_ATTEMPTS = 5  # Max attempts per window
ADMIN_BYPASS_LOCKOUT_DURATION = 900  # 15 minute lockout after exceeding


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token"""
    return secrets.token_urlsafe(32)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    if request.client:
        return request.client.host
    
    return "unknown"


def _is_ip_whitelisted(ip: str) -> bool:
    """
    Check if IP is in the admin bypass whitelist.
    
    Configure via ADMIN_BYPASS_IPS environment variable.
    Format: comma-separated list of IPs or CIDR ranges.
    
    Example: ADMIN_BYPASS_IPS=192.168.1.100,10.0.0.0/8
    """
    whitelist = settings.admin_bypass_ips
    
    if not whitelist:
        logger.warning(
            "admin_bypass_no_whitelist_configured",
            message="ADMIN_BYPASS_IPS not configured - admin bypass disabled"
        )
        return False
    
    # Direct IP match
    if ip in whitelist:
        return True
    
    # CIDR range matching (basic implementation)
    try:
        import ipaddress
        client_ip = ipaddress.ip_address(ip)
        
        for allowed in whitelist:
            if "/" in allowed:
                # It's a CIDR range
                network = ipaddress.ip_network(allowed, strict=False)
                if client_ip in network:
                    return True
    except (ValueError, TypeError):
        # Invalid IP format, deny
        pass
    
    return False


def _check_admin_bypass_rate_limit(ip: str) -> tuple[bool, Optional[str]]:
    """
    Check rate limit for admin bypass attempts.
    
    Returns:
        tuple[bool, Optional[str]]: (allowed, error_message)
    """
    now = time.time()
    
    # Clean old entries
    if ip in _admin_bypass_attempts:
        _admin_bypass_attempts[ip] = [
            (ts, success) for ts, success in _admin_bypass_attempts[ip]
            if now - ts < ADMIN_BYPASS_LOCKOUT_DURATION
        ]
    
    attempts = _admin_bypass_attempts.get(ip, [])
    
    # Check for lockout (too many failed attempts)
    recent_failures = [
        (ts, success) for ts, success in attempts
        if not success and now - ts < ADMIN_BYPASS_LOCKOUT_DURATION
    ]
    
    if len(recent_failures) >= ADMIN_BYPASS_MAX_ATTEMPTS:
        oldest_failure = min(ts for ts, _ in recent_failures)
        lockout_remaining = int(ADMIN_BYPASS_LOCKOUT_DURATION - (now - oldest_failure))
        
        logger.warning(
            "admin_bypass_locked_out",
            ip=ip,
            lockout_remaining_seconds=lockout_remaining
        )
        
        return False, f"Too many failed attempts. Try again in {lockout_remaining} seconds."
    
    # Check rate limit within window
    recent_attempts = [
        (ts, success) for ts, success in attempts
        if now - ts < ADMIN_BYPASS_RATE_LIMIT_WINDOW
    ]
    
    if len(recent_attempts) >= ADMIN_BYPASS_MAX_ATTEMPTS:
        return False, "Rate limit exceeded for admin bypass attempts."
    
    return True, None


def _record_admin_bypass_attempt(ip: str, success: bool) -> None:
    """Record an admin bypass attempt for rate limiting"""
    now = time.time()
    
    if ip not in _admin_bypass_attempts:
        _admin_bypass_attempts[ip] = []
    
    _admin_bypass_attempts[ip].append((now, success))
    
    # Prune old entries to prevent memory growth
    if len(_admin_bypass_attempts[ip]) > 100:
        cutoff = now - ADMIN_BYPASS_LOCKOUT_DURATION
        _admin_bypass_attempts[ip] = [
            (ts, s) for ts, s in _admin_bypass_attempts[ip]
            if ts > cutoff
        ]


async def validate_csrf_token(request: Request) -> None:
    """
    Validate CSRF token for state-changing operations.
    
    Security layers for admin bypass:
    1. IP must be in whitelist (ADMIN_BYPASS_IPS)
    2. Rate limiting on bypass attempts
    3. API key must match exactly
    4. All attempts are logged
    
    Raises:
        HTTPException: If validation fails
    """
    # Skip for safe methods
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return
    
    client_ip = _get_client_ip(request)
    admin_bypass_header = request.headers.get("X-Admin-Bypass-CSRF")
    
    # Admin bypass flow
    if admin_bypass_header:
        # Layer 1: Check IP whitelist
        if not _is_ip_whitelisted(client_ip):
            logger.warning(
                "admin_bypass_ip_not_whitelisted",
                ip=client_ip,
                method=request.method,
                path=request.url.path
            )
            _record_admin_bypass_attempt(client_ip, False)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin bypass not allowed from this IP"
            )
        
        # Layer 2: Check rate limit
        allowed, error_msg = _check_admin_bypass_rate_limit(client_ip)
        if not allowed:
            logger.warning(
                "admin_bypass_rate_limited",
                ip=client_ip,
                method=request.method,
                path=request.url.path
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        # Layer 3: Validate API key
        if not settings.admin_api_key:
            logger.error(
                "admin_bypass_no_api_key_configured",
                ip=client_ip
            )
            _record_admin_bypass_attempt(client_ip, False)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Admin bypass not properly configured"
            )
        
        if secrets.compare_digest(admin_bypass_header, settings.admin_api_key):
            _record_admin_bypass_attempt(client_ip, True)
            logger.info(
                "csrf_bypassed_via_admin_key",
                ip=client_ip,
                method=request.method,
                path=request.url.path
            )
            return
        else:
            _record_admin_bypass_attempt(client_ip, False)
            logger.warning(
                "admin_bypass_invalid_key",
                ip=client_ip,
                method=request.method,
                path=request.url.path
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin bypass key"
            )
    
    # Standard CSRF validation
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