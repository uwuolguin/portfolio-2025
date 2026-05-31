"""
Input Validation Utilities

Centralized validation functions for data integrity and security.
All user input should pass through these validators before processing.
"""

import re
import structlog
from app.utils.exceptions import AppValidationError

logger = structlog.get_logger(__name__)


def normalize_whitespace(value: str) -> str:
    """Strip control characters and collapse internal whitespace to single spaces."""
    if not isinstance(value, str):
        return ""
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def validate_not_empty(value: str, field_name: str, normalize: bool = True) -> str:
    """Ensure a string field is not empty or whitespace-only."""
    if normalize:
        value = normalize_whitespace(value)
    if not value:
        raise AppValidationError(
            field=field_name,
            message="Field cannot be empty or contain only whitespace",
        )
    return value


def validate_length(
    value: str,
    field_name: str,
    min_length: int = 0,
    max_length: int = 1000,
    normalize: bool = True,
) -> str:
    """Validate that a string falls within the allowed length range."""
    if normalize:
        value = normalize_whitespace(value)
    if len(value) < min_length:
        raise AppValidationError(
            field=field_name,
            message=f"Must be at least {min_length} characters",
            value=value[:50] if value else None,
        )
    if len(value) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Must not exceed {max_length} characters",
            value=value[:50],
        )
    return value


def validate_email(value: str, field_name: str = "email") -> str:
    """Validate email format, length, and local-part constraints."""
    value = normalize_whitespace(value).lower()
    if not value:
        raise AppValidationError(field=field_name, message="Email cannot be empty")
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, value):
        raise AppValidationError(
            field=field_name,
            message="Invalid email format",
            value=value[:50],
        )
    if len(value) > 254:
        raise AppValidationError(
            field=field_name,
            message="Email too long (max 254 characters)",
            value=value[:50],
        )
    local_part, _ = value.rsplit('@', 1)
    if len(local_part) > 64:
        raise AppValidationError(
            field=field_name,
            message="Email local part too long",
            value=value[:50],
        )
    return value


def validate_phone(
    value: str,
    field_name: str = "phone",
    min_length: int = 8,
    max_length: int = 20,
) -> str:
    """Validate phone number format and digit count."""
    value = normalize_whitespace(value)
    if not value:
        raise AppValidationError(
            field=field_name,
            message="Phone number cannot be empty",
        )
    if not re.match(r'^[\d\s\-\(\)\+]+$', value):
        raise AppValidationError(
            field=field_name,
            message="Phone number contains invalid characters",
            value=value[:20],
        )
    digits_only = re.sub(r'\D', '', value)
    if len(digits_only) < min_length:
        raise AppValidationError(
            field=field_name,
            message=f"Phone number must have at least {min_length} digits",
            value=value[:20],
        )
    if len(digits_only) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Phone number must not exceed {max_length} digits",
            value=value[:20],
        )
    return value


def validate_name(
    value: str,
    field_name: str = "name",
    min_length: int = 1,
    max_length: int = 100,
) -> str:
    """Validate name length and screen for common XSS / injection patterns."""
    value = normalize_whitespace(value)
    if len(value) < min_length:
        raise AppValidationError(
            field=field_name,
            message=f"Name must be at least {min_length} character(s)",
            value=value[:50] if value else None,
        )
    if len(value) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Name must not exceed {max_length} characters",
            value=value[:50],
        )
    suspicious_patterns = [r'<script', r'javascript:', r'on\w+\s*=', r'data:text/html']
    value_lower = value.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, value_lower):
            logger.warning(
                "suspicious_input_detected",
                field=field_name,
                pattern=pattern,
                value_preview=value[:30],
            )
            raise AppValidationError(
                field=field_name,
                message="Name contains invalid characters",
            )
    return value


def validate_description(
    value: str,
    field_name: str = "description",
    max_length: int = 500,
    allow_empty: bool = False,
) -> str:
    """Validate description length; optionally allow empty values."""
    value = normalize_whitespace(value)
    if not value and not allow_empty:
        raise AppValidationError(
            field=field_name,
            message="Description cannot be empty",
        )
    if len(value) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Description must not exceed {max_length} characters",
            value=value[:50],
        )
    return value


def validate_address(
    value: str,
    field_name: str = "address",
    max_length: int = 200,
) -> str:
    """Validate that an address is non-empty and within the length limit."""
    value = normalize_whitespace(value)
    if not value:
        raise AppValidationError(field=field_name, message="Address cannot be empty")
    if len(value) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Address must not exceed {max_length} characters",
            value=value[:50],
        )
    return value


def validate_password(
    value: str,
    field_name: str = "password",
    min_length: int = 8,
    max_length: int = 100,
) -> str:
    """Validate password presence and length bounds."""
    if not value:
        raise AppValidationError(field=field_name, message="Password cannot be empty")
    if len(value) < min_length:
        raise AppValidationError(
            field=field_name,
            message=f"Password must be at least {min_length} characters",
        )
    if len(value) > max_length:
        raise AppValidationError(
            field=field_name,
            message=f"Password must not exceed {max_length} characters",
        )
    return value


def validate_uuid(value: str, field_name: str = "uuid") -> str:
    """Validate that a string is a well-formed UUID (lowercase, hyphenated)."""
    value = normalize_whitespace(value).lower()
    uuid_pattern = (
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    )
    if not re.match(uuid_pattern, value):
        raise AppValidationError(
            field=field_name,
            message="Invalid UUID format",
            value=value[:50],
        )
    return value


def validate_language(value: str, field_name: str = "lang") -> str:
    """Validate that the language code is one of the supported values (es, en)."""
    value = normalize_whitespace(value).lower()
    if value not in ("es", "en"):
        raise AppValidationError(
            field=field_name,
            message="Language must be 'es' or 'en'",
            value=value,
        )
    return value


def sanitize_for_log(value: str, max_length: int = 50) -> str:
    """Remove control characters and truncate a value before writing it to logs."""
    if not isinstance(value, str):
        return str(value)[:max_length]
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', value)
    if len(sanitized) > max_length:
        return sanitized[:max_length] + "..."
    return sanitized
