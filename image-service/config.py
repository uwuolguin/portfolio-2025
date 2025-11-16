"""
Image Service Configuration
Centralized, type-safe configuration using Pydantic
"""
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Set


class Settings(BaseSettings):
    """
    Image Service Configuration
    
    All settings loaded from environment variables with validation
    Defaults provided for development only
    """
    
    minio_endpoint: str = Field(
        default="minio:9000",
        description="MinIO endpoint (host:port)"
    )
    
    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key (change in production!)"
    )
    
    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key (change in production!)"
    )
    
    minio_bucket: str = Field(
        default="images",
        description="S3 bucket name for image storage"
    )
    
    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO connection"
    )

    max_file_size: int = Field(
        default=10_000_000,  # 10MB
        description="Maximum upload size in bytes",
        ge=1_000_000,  # At least 1MB
        le=50_000_000  # At most 50MB
    )
    
    chunk_size: int = Field(
        default=1024 * 1024,  # 1MB chunks
        description="Streaming chunk size in bytes",
        ge=1024,  # At least 1KB
        le=10 * 1024 * 1024  # At most 10MB
    )
    
    allowed_types: Set[str] = Field(
        default={"image/jpeg", "image/png", "image/webp"},
        description="Allowed MIME types for upload"
    )
    
    # NSFW Detection Settings
    nsfw_enabled: bool = Field(
        default=True,
        description="Enable NSFW content detection"
    )
    
    nsfw_threshold: float = Field(
        default=0.75,
        description="NSFW detection threshold (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    
    nsfw_fail_closed: bool = Field(
        default=True,
        description="Block uploads if NSFW check fails to run"
    )
    
    service_name: str = Field(
        default="Image Storage Service",
        description="Service display name"
    )
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode (disable in production!)"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Show warnings for missing .env
        env_prefix = ""
        
        # Example for documentation
        json_schema_extra = {
            "example": {
                "minio_endpoint": "minio:9000",
                "minio_access_key": "your_access_key",
                "minio_secret_key": "your_secret_key",
                "minio_bucket": "images",
                "max_file_size": 10_000_000,
                "nsfw_enabled": True,
                "nsfw_threshold": 0.75
            }
        }

settings = Settings()