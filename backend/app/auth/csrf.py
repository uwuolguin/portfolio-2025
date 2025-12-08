import secrets
from fastapi import Request, HTTPException, status
import structlog

logger = structlog.get_logger(__name__)


def generate_csrf_token() -> str:
    """Generate a new CSRF token"""
    return secrets.token_urlsafe(32)


async def validate_csrf_token(request: Request) -> None:
    """
    Validate CSRF token for state-changing operations (POST, PUT, DELETE, PATCH)
    
    Supports admin bypass via X-Admin-Bypass-CSRF header:
    - If header present and matches ADMIN_API_KEY, skip CSRF validation
    - Otherwise, perform standard CSRF validation
    
    Raises HTTPException if validation fails
    """
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return
    
    admin_bypass_header = request.headers.get("X-Admin-Bypass-CSRF")
    
    if admin_bypass_header:
        from app.config import settings
        
        if settings.admin_api_key and secrets.compare_digest(
            admin_bypass_header, 
            settings.admin_api_key
        ):
            logger.info(
                "csrf_bypassed_via_admin_key",
                method=request.method,
                path=request.url.path
            )
            return
        else:
            logger.warning(
                "csrf_bypass_attempted_with_invalid_key",
                method=request.method,
                path=request.url.path
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin bypass key"
            )
    
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    
    if not cookie_token or not header_token:
        logger.warning("csrf_validation_failed", reason="missing_tokens")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing"
        )
    
    if not secrets.compare_digest(cookie_token, header_token):
        logger.warning("csrf_validation_failed", reason="token_mismatch")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid"
        )
    
    logger.debug("csrf_validation_success")