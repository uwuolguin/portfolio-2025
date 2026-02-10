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
        
        response.headers["X-Frame-Options"] = "DENY"

        response.headers["X-Content-Type-Options"] = "nosniff"
        
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
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
        
        from app.config import settings
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        for header in ["Server", "X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version"]:
            if header in response.headers:
                del response.headers[header]
        
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    HTTPS redirect middleware (TEMPORARILY DISABLED).

    FIXME:
    This middleware is intentionally disabled because the application is
    currently running directly inside Kubernetes WITHOUT a TLS-terminating
    reverse proxy (Ingress).

    Problem:
    - Kubernetes liveness/readiness probes use HTTP
    - Internal pod-to-pod traffic uses HTTP
    - Redirecting these requests causes 301 responses and breaks pod readiness

    Re-enable ONLY when:
    - An Ingress (Traefik / NGINX / Cloud LB) is added
    - TLS is terminated at the Ingress
    - X-Forwarded-Proto=https is correctly set by the proxy
    - Health probes are explicitly excluded or handled at the Ingress level
    """

    async def dispatch(self, request: Request, call_next):
        # TEMPORARILY DISABLED — pass-through only
        return await call_next(request)