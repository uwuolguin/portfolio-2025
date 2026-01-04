"""
Input Validation Utilities

Centralized validation functions for data integrity and security.
All user input should pass through these validators before processing.

Features:
- Whitespace normalization and validation
- Length validation
- Format validation (email, phone, etc.)
- XSS prevention (output encoding handled elsewhere)
"""

import re
from typing import Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures"""
    def __init__(self, field: str, message: str, value: Optional[str] = None):
        self.field = field
        self.message = message
        self.value = value  # Truncated for logging
        super().__init__(f"{field}: {message}")


def normalize_whitespace(value: str) -> str:
    """
    Normalize whitespace in a string.
    
    - Strips leading/trailing whitespace
    - Collapses multiple spaces into single space
    - Removes control characters
    
    Args:
        value: Input string
        
    Returns:
        Normalized string
    """
    if not isinstance(value, str):
        return ""
    
    # Remove control characters (except newline/tab in some cases)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    
    # Collapse multiple whitespace into single space
    value = re.sub(r'\s+', ' ', value)
    
    # Strip leading/trailing
    return value.strip()


def validate_not_empty(
    value: str,
    field_name: str,
    normalize: bool = True
) -> str:
    """
    Validate that a string is not empty after normalization.
    
    Args:
        value: Input string
        field_name: Name of field for error messages
        normalize: Whether to normalize whitespace
        
    Returns:
        Validated (and optionally normalized) string
        
    Raises:
        ValidationError: If value is empty
    """
    if normalize:
        value = normalize_whitespace(value)
    
    if not value:
        raise ValidationError(
            field=field_name,
            message="Field cannot be empty or contain only whitespace"
        )
    
    return value


def validate_length(
    value: str,
    field_name: str,
    min_length: int = 0,
    max_length: int = 1000,
    normalize: bool = True
) -> str:
    """
    Validate string length within bounds.
    
    Args:
        value: Input string
        field_name: Name of field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        normalize: Whether to normalize whitespace first
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If length constraints violated
    """
    if normalize:
        value = normalize_whitespace(value)
    
    if len(value) < min_length:
        raise ValidationError(
            field=field_name,
            message=f"Must be at least {min_length} characters",
            value=value[:50] if value else None
        )
    
    if len(value) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Must not exceed {max_length} characters",
            value=value[:50]
        )
    
    return value


def validate_email(value: str, field_name: str = "email") -> str:
    """
    Validate and normalize email address.
    
    Args:
        value: Input email
        field_name: Name of field for error messages
        
    Returns:
        Validated and normalized email (lowercase, stripped)
        
    Raises:
        ValidationError: If email format is invalid
    """
    value = normalize_whitespace(value).lower()
    
    if not value:
        raise ValidationError(
            field=field_name,
            message="Email cannot be empty"
        )
    
    # Basic email regex - not perfect but catches obvious issues
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, value):
        raise ValidationError(
            field=field_name,
            message="Invalid email format",
            value=value[:50]
        )
    
    # Additional checks
    if len(value) > 254:  # RFC 5321
        raise ValidationError(
            field=field_name,
            message="Email too long (max 254 characters)",
            value=value[:50]
        )
    
    local_part, domain = value.rsplit('@', 1)
    
    if len(local_part) > 64:
        raise ValidationError(
            field=field_name,
            message="Email local part too long",
            value=value[:50]
        )
    
    return value


def validate_phone(
    value: str,
    field_name: str = "phone",
    min_length: int = 8,
    max_length: int = 20
) -> str:
    """
    Validate and normalize phone number.
    
    Allows: digits, spaces, hyphens, parentheses, plus sign
    
    Args:
        value: Input phone number
        field_name: Name of field for error messages
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Validated phone number (whitespace normalized)
        
    Raises:
        ValidationError: If phone format is invalid
    """
    value = normalize_whitespace(value)
    
    if not value:
        raise ValidationError(
            field=field_name,
            message="Phone number cannot be empty"
        )
    
    # Check for valid characters
    if not re.match(r'^[\d\s\-\(\)\+]+$', value):
        raise ValidationError(
            field=field_name,
            message="Phone number contains invalid characters",
            value=value[:20]
        )
    
    # Check digit count (remove non-digits)
    digits_only = re.sub(r'\D', '', value)
    
    if len(digits_only) < min_length:
        raise ValidationError(
            field=field_name,
            message=f"Phone number must have at least {min_length} digits",
            value=value[:20]
        )
    
    if len(digits_only) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Phone number must not exceed {max_length} digits",
            value=value[:20]
        )
    
    return value


def validate_name(
    value: str,
    field_name: str = "name",
    min_length: int = 1,
    max_length: int = 100
) -> str:
    """
    Validate a name field (person name, company name, etc.)
    
    Args:
        value: Input name
        field_name: Name of field for error messages
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Validated and normalized name
        
    Raises:
        ValidationError: If validation fails
    """
    value = normalize_whitespace(value)
    
    if len(value) < min_length:
        raise ValidationError(
            field=field_name,
            message=f"Name must be at least {min_length} character(s)",
            value=value[:50] if value else None
        )
    
    if len(value) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Name must not exceed {max_length} characters",
            value=value[:50]
        )
    
    # Check for suspicious patterns (potential injection)
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'on\w+\s*=',  # event handlers
        r'data:text/html',
    ]
    
    value_lower = value.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, value_lower):
            logger.warning(
                "suspicious_input_detected",
                field=field_name,
                pattern=pattern,
                value_preview=value[:30]
            )
            raise ValidationError(
                field=field_name,
                message="Name contains invalid characters"
            )
    
    return value


def validate_description(
    value: str,
    field_name: str = "description",
    max_length: int = 500,
    allow_empty: bool = False
) -> str:
    """
    Validate a description/text field.
    
    Args:
        value: Input description
        field_name: Name of field for error messages
        max_length: Maximum length
        allow_empty: Whether empty values are allowed
        
    Returns:
        Validated and normalized description
        
    Raises:
        ValidationError: If validation fails
    """
    value = normalize_whitespace(value)
    
    if not value and not allow_empty:
        raise ValidationError(
            field=field_name,
            message="Description cannot be empty"
        )
    
    if len(value) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Description must not exceed {max_length} characters",
            value=value[:50]
        )
    
    return value


def validate_address(
    value: str,
    field_name: str = "address",
    max_length: int = 200
) -> str:
    """
    Validate an address field.
    
    Args:
        value: Input address
        field_name: Name of field for error messages
        max_length: Maximum length
        
    Returns:
        Validated and normalized address
        
    Raises:
        ValidationError: If validation fails
    """
    value = normalize_whitespace(value)
    
    if not value:
        raise ValidationError(
            field=field_name,
            message="Address cannot be empty"
        )
    
    if len(value) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Address must not exceed {max_length} characters",
            value=value[:50]
        )
    
    return value


def validate_password(
    value: str,
    field_name: str = "password",
    min_length: int = 8,
    max_length: int = 100
) -> str:
    """
    Validate password strength.
    
    NOTE: We do NOT normalize passwords to preserve exact input.
    
    Args:
        value: Input password
        field_name: Name of field for error messages
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Original password (not modified)
        
    Raises:
        ValidationError: If validation fails
    """
    # Don't normalize - preserve exact password
    if not value:
        raise ValidationError(
            field=field_name,
            message="Password cannot be empty"
        )
    
    if len(value) < min_length:
        raise ValidationError(
            field=field_name,
            message=f"Password must be at least {min_length} characters"
        )
    
    if len(value) > max_length:
        raise ValidationError(
            field=field_name,
            message=f"Password must not exceed {max_length} characters"
        )
    
    return value


def validate_uuid(value: str, field_name: str = "uuid") -> str:
    """
    Validate UUID format.
    
    Args:
        value: Input UUID string
        field_name: Name of field for error messages
        
    Returns:
        Validated UUID string (lowercase)
        
    Raises:
        ValidationError: If UUID format is invalid
    """
    value = normalize_whitespace(value).lower()
    
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if not re.match(uuid_pattern, value):
        raise ValidationError(
            field=field_name,
            message="Invalid UUID format",
            value=value[:50]
        )
    
    return value


def validate_language(value: str, field_name: str = "lang") -> str:
    """
    Validate language code.
    
    Args:
        value: Language code (es or en)
        field_name: Name of field for error messages
        
    Returns:
        Validated language code
        
    Raises:
        ValidationError: If language code is invalid
    """
    value = normalize_whitespace(value).lower()
    
    if value not in ("es", "en"):
        raise ValidationError(
            field=field_name,
            message="Language must be 'es' or 'en'",
            value=value
        )
    
    return value


def sanitize_for_log(value: str, max_length: int = 50) -> str:
    """
    Sanitize a value for safe logging.
    
    Truncates and removes potentially dangerous characters.
    
    Args:
        value: Input value
        max_length: Maximum length for log output
        
    Returns:
        Sanitized string safe for logging
    """
    if not isinstance(value, str):
        return str(value)[:max_length]
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', value)
    
    # Truncate
    if len(sanitized) > max_length:
        return sanitized[:max_length] + "..."
    
    return sanitized