"""
Image Validation and NSFW Detection Module
Handles image processing, optimization, and content moderation
"""

from typing import Tuple
from io import BytesIO

import structlog
from PIL import Image, UnidentifiedImageError

from config import settings

logger = structlog.get_logger(__name__)


class ImageValidator:
    """
    Image validation and NSFW detection

    Features:
    - Format validation (JPEG, PNG, WebP)
    - Size validation (max configured in MAX_FILE_SIZE)
    - Dimension validation (max MAX_WIDTH x MAX_HEIGHT)
    - Image optimization (compression, progressive JPEG)
    - NSFW content detection
    """

    _nsfw_model_loaded = False
    _nsfw_available = False

    @classmethod
    def init_nsfw_model(cls) -> bool:
        """
        Initialize NSFW model once at startup
        Returns True if successful, False otherwise
        Gracefully handles failure - app continues without NSFW protection
        """
        if not settings.nsfw_enabled:
            logger.info("nsfw_detection_disabled", reason="config_setting")
            cls._nsfw_available = False
            return False

        if cls._nsfw_model_loaded:
            logger.info("nsfw_model_already_loaded")
            return cls._nsfw_available

        try:
            logger.info("nsfw_model_loading_starting")

            from opennsfw2 import predict_image

            logger.info("nsfw_model_testing")
            test_img = Image.new("RGB", (224, 224), color="red")
            test_bytes = BytesIO()
            test_img.save(test_bytes, format="JPEG")
            test_bytes.seek(0)

            test_score = predict_image(test_bytes)

            logger.info(
                "nsfw_model_loaded_successfully",
                test_score=float(test_score),
                threshold=settings.nsfw_threshold,
            )

            cls._nsfw_model_loaded = True
            cls._nsfw_available = True
            return True

        except ImportError as e:
            logger.error(
                "nsfw_model_import_failed",
                error=str(e),
                message="Install with: pip install opennsfw2",
            )
            cls._nsfw_available = False
            return False

        except Exception as e:
            logger.error("nsfw_model_load_failed", error=str(e), exc_info=True)
            cls._nsfw_available = False
            return False

    @classmethod
    def get_nsfw_status(cls) -> dict:
        """Get current NSFW checking status"""
        return {
            "enabled": settings.nsfw_enabled,
            "available": cls._nsfw_available,
            "model_loaded": cls._nsfw_model_loaded,
            "threshold": settings.nsfw_threshold,
            "fail_closed": settings.nsfw_fail_closed,
        }

    @classmethod
    def validate_and_process_image(
        cls,
        file_bytes: bytes,
        content_type: str,
    ) -> Tuple[bytes, str]:
        """
        Validate and process image synchronously

        Steps:
        1. Validate MIME type
        2. Check file size
        3. Open and validate image
        4. Check dimensions
        5. Convert to RGB if needed
        6. Optimize and compress

        Returns: (processed_bytes, extension)
        Raises: ValueError on validation failure
        """

        # Validate MIME type
        if content_type not in settings.allowed_types:
            raise ValueError(
                f"Unsupported MIME type: {content_type}. "
                f"Allowed: {', '.join(sorted(settings.allowed_types))}"
            )

        # Check size before processing
        if len(file_bytes) > settings.max_file_size:
            size_mb = len(file_bytes) / 1_048_576
            limit_mb = settings.max_file_size / 1_048_576
            raise ValueError(
                f"Image too large ({size_mb:.2f}MB). Limit: {limit_mb:.2f}MB"
            )

        # Open and validate image
        try:
            with Image.open(BytesIO(file_bytes)) as img:
                img.load()  # Force full load to detect corruption
                fmt = (img.format or "").upper()
                img_copy = img.copy()
        except UnidentifiedImageError:
            raise ValueError("Invalid or corrupted image file")
        except Exception as e:
            raise ValueError(f"Image processing error: {str(e)}")

        # Validate format (PIL level)
        if fmt not in settings.allowed_formats:
            raise ValueError(
                f"Unsupported format: {fmt}. "
                f"Allowed: {', '.join(sorted(settings.allowed_formats))}"
            )

        # Check dimensions
        if (
            img_copy.width > settings.max_width
            or img_copy.height > settings.max_height
        ):
            raise ValueError(
                f"Image too large ({img_copy.width}x{img_copy.height}). "
                f"Max: {settings.max_width}x{settings.max_height}"
            )

        # Convert RGBA/palette to RGB (avoid transparency issues)
        if img_copy.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img_copy.size, (255, 255, 255))
            if img_copy.mode == "P":
                img_copy = img_copy.convert("RGBA")
            background.paste(img_copy, mask=img_copy.split()[-1])
            img_copy = background

        # Optimize and save
        out = BytesIO()

        save_params = {}
        if fmt == "JPEG":
            save_params = {
                "quality": 90,
                "optimize": True,
                "progressive": True,  # Better for web streaming
            }
        elif fmt == "PNG":
            save_params = {
                "optimize": True,
                "compress_level": 6,  # Good balance of speed/size
            }
        else:  # WEBP or others configured
            save_params = {
                "quality": 90,
                "method": 6,  # Best compression
            }

        img_copy.save(out, format=fmt, **save_params)

        processed_bytes = out.getvalue()
        ext = settings.ext_by_format.get(fmt, ".jpg")

        logger.info(
            "image_validated_and_processed",
            format=fmt,
            original_size_kb=len(file_bytes) / 1024,
            processed_size_kb=len(processed_bytes) / 1024,
            compression_ratio=f"{(1 - len(processed_bytes) / len(file_bytes)) * 100:.1f}%",
            dimensions=f"{img_copy.width}x{img_copy.height}",
        )

        return processed_bytes, ext

    @classmethod
    def check_nsfw_content(cls, image_bytes: bytes) -> Tuple[float, bool]:
        """
        Run NSFW detection on processed image bytes

        Returns: (score, check_performed)
        - score: 0.0-1.0 (higher = more NSFW)
        - check_performed: True if check ran successfully

        Behavior:
        - If NSFW disabled: returns (0.0, False)
        - If NSFW unavailable and fail_closed: returns (1.0, False) - blocks upload
        - If NSFW unavailable and not fail_closed: returns (0.0, False) - allows upload
        - If check succeeds: returns (actual_score, True)
        - If check fails: same as unavailable
        """
        if not settings.nsfw_enabled:
            return (0.0, False)

        if not cls._nsfw_available:
            if settings.nsfw_fail_closed:
                logger.warning("nsfw_unavailable_blocking_upload")
                return (1.0, False)
            else:
                logger.warning("nsfw_unavailable_allowing_upload")
                return (0.0, False)

        try:
            from opennsfw2 import predict_image

            img_stream = BytesIO(image_bytes)
            score = predict_image(img_stream)

            logger.info(
                "nsfw_check_completed",
                score=float(score),
                threshold=settings.nsfw_threshold,
                will_block=score > settings.nsfw_threshold,
            )

            return float(score), True

        except Exception as e:
            logger.error("nsfw_check_execution_failed", error=str(e), exc_info=True)

            # On error, use fail_closed setting
            if settings.nsfw_fail_closed:
                logger.warning("nsfw_check_failed_blocking_upload")
                return (1.0, False)
            else:
                logger.warning("nsfw_check_failed_allowing_upload")
                return (0.0, False)
