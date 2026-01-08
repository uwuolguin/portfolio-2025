"""
HTTP Exception Handlers

Centralized error handling for consistent API responses.
Provides detailed error information in debug mode while
keeping responses secure in production.

Features:
- Consistent error response format
- Correlation ID tracking
- Safe error messages (no internal details in production)
- Comprehensive logging for debugging
"""

import traceback
from typing import Optional, Any, Dict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
import structlog

from app.config import settings
from app.utils.validators import ValidationError as AppValidationError

logger = structlog.get_logger(__name__)


class APIError(Exception):
    """
    Base exception for API errors.
    
    Provides a consistent structure for all API errors with:
    - HTTP status code
    - User-friendly message
    - Optional detailed error info (debug only)
    - Error code for client handling
    """
    
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code or self._derive_error_code(status_code)
        self.details = details
        self.headers = headers
        super().__init__(message)
    
    @staticmethod
    def _derive_error_code(status_code: int) -> str:
        """Derive error code from HTTP status"""
        codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT",
        }
        return codes.get(status_code, "UNKNOWN_ERROR")


class NotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with identifier '{identifier}' not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class ConflictError(APIError):
    """Resource conflict error (e.g., duplicate)"""
    def __init__(self, message: str, resource: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            error_code="RESOURCE_CONFLICT",
            details={"resource": resource} if resource else None
        )


class UnauthorizedError(APIError):
    """Authentication required error"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_code="AUTHENTICATION_REQUIRED"
        )


class ForbiddenError(APIError):
    """Permission denied error"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            error_code="PERMISSION_DENIED"
        )


class ValidationErrorResponse(APIError):
    """Input validation error"""
    def __init__(self, message: str, field: Optional[str] = None, errors: Optional[list] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, "errors": errors}
        )


class RateLimitError(APIError):
    """Rate limit exceeded error"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            headers=headers
        )


class ServiceUnavailableError(APIError):
    """External service unavailable error"""
    def __init__(self, service: str, message: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=message or f"Service temporarily unavailable: {service}",
            error_code="SERVICE_UNAVAILABLE",
            details={"service": service}
        )


def _get_correlation_id(request: Request) -> str:
    """Extract correlation ID from request"""
    return request.headers.get("X-Correlation-ID", "unknown")


def _build_error_response(
    status_code: int,
    message: str,
    error_code: str,
    correlation_id: str,
    details: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build consistent error response structure.
    
    In debug mode, includes additional details.
    In production, keeps responses minimal and secure.
    """
    response = {
        "error": {
            "code": error_code,
            "message": message,
        },
        "correlation_id": correlation_id,
    }
    
    if settings.debug:
        response["error"]["details"] = details
        response["error"]["path"] = path
    
    return response


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handler for APIError exceptions"""
    correlation_id = _get_correlation_id(request)
    
    logger.warning(
        "api_error",
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id,
        details=exc.details
    )
    
    response_content = _build_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.error_code,
        correlation_id=correlation_id,
        details=exc.details,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers=exc.headers
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """Handler for FastAPI HTTPException"""
    correlation_id = _get_correlation_id(request)
    
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id
    )
    
    error_code = APIError._derive_error_code(exc.status_code)
    
    response_content = _build_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        error_code=error_code,
        correlation_id=correlation_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers=getattr(exc, "headers", None)
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handler for Pydantic validation errors"""
    correlation_id = _get_correlation_id(request)
    
    # Extract field-level errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        "validation_error",
        errors=errors,
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id
    )
    
    # User-friendly message
    if len(errors) == 1:
        message = f"Validation error in '{errors[0]['field']}': {errors[0]['message']}"
    else:
        message = f"Validation errors in {len(errors)} field(s)"
    
    response_content = _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message=message,
        error_code="VALIDATION_ERROR",
        correlation_id=correlation_id,
        details={"errors": errors} if settings.debug else None,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=response_content
    )


async def app_validation_error_handler(
    request: Request,
    exc: AppValidationError
) -> JSONResponse:
    """Handler for custom app ValidationError"""
    correlation_id = _get_correlation_id(request)
    
    logger.warning(
        "app_validation_error",
        field=exc.field,
        message=exc.message,
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id
    )
    
    response_content = _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message=f"Validation error: {exc.message}",
        error_code="VALIDATION_ERROR",
        correlation_id=correlation_id,
        details={"field": exc.field},
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=response_content
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handler for unhandled exceptions.
    
    SECURITY: Never expose internal error details in production.
    """
    correlation_id = _get_correlation_id(request)
    
    # Log full details for debugging
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id,
        traceback=traceback.format_exc()
    )
    
    # Build response - minimal info in production
    if settings.debug:
        message = f"Internal error: {type(exc).__name__}: {str(exc)}"
        details = {
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc().split("\n")
        }
    else:
        message = "An unexpected error occurred. Please try again later."
        details = None
    
    response_content = _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        error_code="INTERNAL_ERROR",
        correlation_id=correlation_id,
        details=details,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Call this during app initialization.
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppValidationError, app_validation_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("exception_handlers_registered")