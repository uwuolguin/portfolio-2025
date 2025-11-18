from typing import Set, Dict

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Image Service Configuration
    """

    # =========================================================================
    # MinIO Storage
    # =========================================================================
    minio_endpoint: str = Field(
        default="minio:9000",
        description="MinIO endpoint (host:port)",
    )

    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key (change in production!)",
    )

    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key (change in production!)",
    )

    minio_bucket: str = Field(
        default="images",
        description="S3 bucket name for image storage",
    )

    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO connection",
    )

    # =========================================================================
    # Image Settings
    # =========================================================================
    max_file_size: int = Field(
        default=10_000_000,
        description="Maximum upload size in bytes",
        ge=1_000_000,
        le=50_000_000,
    )

    chunk_size: int = Field(
        default=102_400,
        description="Streaming chunk size in bytes",
        ge=1024,
        le=10 * 1024 * 1024,
    )

    max_width: int = Field(
        default=4000,
        description="Maximum image width in pixels",
        ge=1,
        le=20_000,
    )

    max_height: int = Field(
        default=4000,
        description="Maximum image height in pixels",
        ge=1,
        le=20_000,
    )

    allowed_types: Set[str] = Field(
        default={"image/jpeg", "image/png"},
        description="Allowed MIME types for upload",
    )

    allowed_formats: Set[str] = Field(
        default={"JPEG", "PNG"},
        description="Allowed PIL image formats",
    )

    ext_by_format: Dict[str, str] = Field(
        default_factory=lambda: {"JPEG": ".jpg", "PNG": ".png"},
        description="File extension mapping for each image format",
    )
    content_type_map: Dict[str, str] = Field(
        default_factory=lambda: {".jpg": "image/jpeg",".jpeg": "image/jpeg",".png": "image/png"},
        description="image format mapping for each File extension",
    )


    # =========================================================================
    # NSFW Settings
    # =========================================================================
    nsfw_enabled: bool = Field(
        default=True,
        description="Enable NSFW content detection",
    )

    nsfw_threshold: float = Field(
        default=0.75,
        description="NSFW detection threshold (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    nsfw_fail_closed: bool = Field(
        default=True,
        description="Block uploads if NSFW check fails to run",
    )

    # =========================================================================
    # Service Settings
    # =========================================================================
    service_name: str = Field(
        default="Image Storage Service",
        description="Service display name",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode (disable in production!)",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = ""


settings = Settings()