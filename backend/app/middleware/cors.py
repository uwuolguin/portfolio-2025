from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import structlog

logger = structlog.get_logger(__name__)

def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware with secure settings
    
    IMPORTANT: For production, update allowed_origins in your .env file
    to include only your actual frontend domains (no wildcards)
    """
    allowed_origins = settings.allowed_origins
    
    if "*" in allowed_origins and not settings.debug:
        logger.critical(
            "cors_security_warning",
            message="Wildcard CORS origin detected in production! This is a security risk.",
            allowed_origins=allowed_origins
        )
    
    logger.info(
        "cors_configuration",
        allowed_origins=allowed_origins,
        credentials_allowed=True,
        debug_mode=settings.debug
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins, 
        allow_credentials=True, 
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], 
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Correlation-ID",
            "X-CSRF-Token",
            "Accept",
            "Accept-Language",
            "Origin",
            "Referer",
            "User-Agent"
        ],
        expose_headers=[
            "X-Correlation-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ],
        max_age=600, 
    )
    
    
    if settings.debug and "http://localhost" in allowed_origins:
        logger.warning(
            "cors_development_mode",
            message="Running with development CORS settings. DO NOT use in production!"
        )