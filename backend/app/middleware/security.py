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
    Force HTTPS in production
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

    """
    Basic rate limiting middleware
    
    WARNING: This is a simple in-memory implementation for development/testing.
    For production with multiple workers/containers, use Redis-based rate limiting
    (see app.cache.rate_limit.py for the proper implementation).
    """
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts = {}  # {client_ip: [(timestamp, count), ...]}
        
        logger.warning(
            "rate_limit_middleware_initialized",
            implementation="in-memory",
            note="Use Redis-based rate limiting for production"
        )
    
    async def dispatch(self, request: Request, call_next):
        from time import time
        
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        
        current_time = time()
        
        # Clean up old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                (ts, count) for ts, count in self.request_counts[client_ip]
                if current_time - ts < self.window_seconds
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Count requests in current window
        total_requests = sum(count for _, count in self.request_counts[client_ip])
        
        # Check if limit exceeded
        if total_requests >= self.max_requests:
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
                requests=total_requests,
                window=self.window_seconds
            )
            return Response(
                content='{"detail": "Too many requests. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(current_time + self.window_seconds))
                }
            )
        
        # Record this request
        self.request_counts[client_ip].append((current_time, 1))
        
        # Add rate limit headers to response
        response = await call_next(request)
        remaining = self.max_requests - total_requests - 1
        
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_seconds))
        
        return response