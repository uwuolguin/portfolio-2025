from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, RedirectResponse
import structlog

logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enhanced security headers for production environment
    Protects against common web vulnerabilities
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS filter (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        
        # Content Security Policy (skip for API docs)
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "  
                "style-src 'self' 'unsafe-inline'; " 
                "img-src 'self' data: https:; " 
                "font-src 'self'; "
                "connect-src 'self'; "  
                "frame-ancestors 'none'; " 
                "base-uri 'self'; "  
                "form-action 'self'; " 
                "upgrade-insecure-requests;" 
            )
        
        # HSTS (only in production)
        from app.config import settings
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Remove server identification headers
        for header in ["Server", "X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version"]:
            if header in response.headers:
                del response.headers[header]
        
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Force HTTPS in production.
    If debug is False, this middleware ensures that requests are served over HTTPS.

    Behavior:
    - In development (settings.debug=True): passthrough, no redirect.
    - If request is already HTTPS (request.url.scheme == "https"): passthrough.
    - If behind a reverse proxy that sets X-Forwarded-Proto=https: passthrough.
    - Otherwise: redirect to the same URL with scheme="https" using a 301.
    """
    
    async def dispatch(self, request: Request, call_next):
        from app.config import settings
        
        # Skip in development
        if settings.debug:
            return await call_next(request)
        
        # Already HTTPS
        if request.url.scheme == "https":
            return await call_next(request)
        
        # Check if behind reverse proxy
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto == "https":
            return await call_next(request)
        
        # Redirect to HTTPS
        https_url = request.url.replace(scheme="https")
        logger.warning(
            "https_redirect",
            original_url=str(request.url),
            redirect_url=str(https_url),
            client_ip=request.client.host if request.client else None
        )
        
        return RedirectResponse(url=str(https_url), status_code=301)