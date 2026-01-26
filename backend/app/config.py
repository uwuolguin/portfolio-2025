"""
Application Configuration

Centralized settings management using pydantic-settings.
All sensitive values should be loaded from environment variables.

SECURITY NOTE: Never commit .env files with real credentials!

UPDATED: Added database_url_primary and database_url_replica for read/write splitting
"""

from typing import Optional, List, Dict, Set

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------------
    # Database - Primary (Writes)
    # ------------------------------------------------------------------------
    database_url: str  # Legacy - used as primary
    alembic_database_url: str  # For migrations - always points to primary
    
    # Optional explicit URLs (if not set, derived from database_url)
    database_url_primary: Optional[str] = None
    database_url_replica: Optional[str] = None
    
    @computed_field
    @property
    def effective_database_url_primary(self) -> str:
        """Get the primary database URL for writes"""
        if self.database_url_primary:
            return self.database_url_primary
        # Default: use database_url as primary
        return self.database_url
    
    @computed_field  
    @property
    def effective_database_url_replica(self) -> str:
        """Get the replica database URL for reads"""
        if self.database_url_replica:
            return self.database_url_replica
        # Default: derive replica URL from primary by replacing host
        # This assumes postgres-primary -> postgres-replica naming
        primary_url = self.effective_database_url_primary
        return primary_url.replace("postgres-primary", "postgres-replica")
    
    # Pool settings
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_pool_max_queries: int = 50_000
    db_pool_max_inactive: float = 300.0
    db_timeout: int = 30
    db_command_timeout: int = 60
    db_server_timeout: int = 60

    db_ssl_mode: str = "require"
    db_ssl_cert_path: Optional[str] = None
    db_ssl_key_path: Optional[str] = None

    # ------------------------------------------------------------------------
    # Redis / Cache
    # ------------------------------------------------------------------------
    redis_url: str
    redis_timeout: int = 5
    cache_ttl: int = 3600
    redis_ssl: bool = False

    # ------------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------------
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # ------------------------------------------------------------------------
    # Admin Bypass Security
    # ------------------------------------------------------------------------
    admin_api_key: str
    admin_bypass_ips: Set[str] = Field(
        default_factory=set,
        description="Comma-separated list of IPs/CIDRs allowed for admin bypass"
    )
    
    @field_validator("admin_bypass_ips", mode="before")
    @classmethod
    def parse_admin_bypass_ips(cls, v):
        """Parse comma-separated IP list into a set"""
        if isinstance(v, set):
            return v
        if isinstance(v, str):
            if not v.strip():
                return set()
            return {ip.strip() for ip in v.split(",") if ip.strip()}
        if isinstance(v, (list, tuple)):
            return set(v)
        return set()

    # ------------------------------------------------------------------------
    # File uploads / Image processing
    # ------------------------------------------------------------------------
    content_type_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "image/jpeg": ".jpg",
            "image/png": ".png",
        }
    )
    max_file_size: int = 10_000_000  # 10MB

    # ------------------------------------------------------------------------
    # Image Service / HTTP client
    # ------------------------------------------------------------------------
    image_service_url: str = "http://image-service:8080"
    request_timeout: float = 30.0
    connection_timeout: float = 5.0
    max_retries: int = 3
    max_connections: int = 100
    max_keepalive_connections: int = 20

    # ------------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Proveo API"
    debug: bool = True
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:80"]
    )

    # ------------------------------------------------------------------------
    # Input Validation
    # ------------------------------------------------------------------------
    max_name_length: int = 100
    max_email_length: int = 100
    max_description_length: int = 500
    max_address_length: int = 200
    max_phone_length: int = 20
    min_password_length: int = 8
    max_password_length: int = 100

    # ------------------------------------------------------------------------
    # Database monitoring / Retry
    # ------------------------------------------------------------------------
    db_health_check_interval: int = 30
    db_slow_query_threshold: float = 1.0
    db_retry_attempts: int = 3
    db_retry_wait_multiplier: float = 0.5
    db_retry_max_wait: float = 5.0

    # ------------------------------------------------------------------------
    # Email / Admin
    # ------------------------------------------------------------------------
    verification_token_email_time: int = 30
    admin_email: str
    resend_api_key: str
    email_from: str = "noreply@proveo.com"
    api_base_url: str = "http://localhost"


# Create a property-based wrapper for backward compatibility
class SettingsWrapper:
    """Wrapper to provide computed properties as regular attributes"""
    
    def __init__(self):
        self._settings = Settings()
    
    def __getattr__(self, name):
        if name == "database_url_primary":
            return self._settings.effective_database_url_primary
        elif name == "database_url_replica":
            return self._settings.effective_database_url_replica
        return getattr(self._settings, name)


settings = SettingsWrapper()