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
    - Format validation (JPEG, PNG)
    - Size validation
    - Dimension validation
    - Image optimization
    - NSFW content detection
    """

    _nsfw_model_loaded = False
    _nsfw_available = False

    @classmethod
    def init_nsfw_model(cls) -> bool:
        """Initialize NSFW model once at startup"""
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
        file_obj,
        content_type: str,
        extension: str
    ) -> BytesIO:
        if content_type not in settings.allowed_types:
            raise ValueError(
                f"Unsupported MIME type: {content_type}. "
                f"Allowed: {', '.join(sorted(settings.allowed_types))}"
            )

        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0)
        if size > settings.max_file_size:
            size_mb = size / 1_048_576
            limit_mb = settings.max_file_size / 1_048_576
            raise ValueError(
                f"Image too large ({size_mb:.2f}MB). Limit: {limit_mb:.2f}MB"
            )

        try:
            with Image.open(file_obj) as img:
                img.load()
                fmt = (img.format or "").upper()
                img_copy = img.copy()
        except UnidentifiedImageError:
            raise ValueError("Invalid or corrupted image file")
        except Exception as e:
            raise ValueError(f"Image processing error: {str(e)}")

        expected_format = None
        for format_name, ext in settings.ext_by_format.items():
            if ext == extension:
                expected_format = format_name
                break

        if not expected_format:
            raise ValueError(f"Unknown extension: {extension}")

        if fmt != expected_format:
            raise ValueError(
                f"Image format mismatch: file is {fmt} but extension is {extension} "
                f"(expected {expected_format})"
            )

        if img_copy.width > settings.max_width or img_copy.height > settings.max_height:
            raise ValueError(
                f"Image too large ({img_copy.width}x{img_copy.height}). "
                f"Max: {settings.max_width}x{settings.max_height}"
            )

        if img_copy.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img_copy.size, (255, 255, 255))
            if img_copy.mode == "P":
                img_copy = img_copy.convert("RGBA")
            background.paste(img_copy, mask=img_copy.split()[-1])
            img_copy = background

        out = BytesIO()
        save_params = {}
        if expected_format == "JPEG":
            save_params = {"quality": 90, "optimize": True, "progressive": True}
        elif expected_format == "PNG":
            save_params = {"optimize": True, "compress_level": 6}

        img_copy.save(out, format=expected_format, **save_params)
        out.seek(0)

        logger.info(
            "image_validated_and_processed",
            format=expected_format,
            extension=extension,
            original_size_kb=size / 1024,
            processed_size_kb=out.getbuffer().nbytes / 1024,
            compression_ratio=f"{(1 - out.getbuffer().nbytes / size) * 100:.1f}%",
            dimensions=f"{img_copy.width}x{img_copy.height}",
        )

        return out

    @classmethod
    def check_nsfw_content(cls, image_stream) -> Tuple[float, bool]:
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

            score = predict_image(image_stream)
            image_stream.seek(0)

            logger.info(
                "nsfw_check_completed",
                score=float(score),
                threshold=settings.nsfw_threshold,
                will_block=score > settings.nsfw_threshold,
            )

            return float(score), True

        except Exception as e:
            logger.error("nsfw_check_execution_failed", error=str(e), exc_info=True)

            if settings.nsfw_fail_closed:
                logger.warning("nsfw_check_failed_blocking_upload")
                return (1.0, False)
            else:
                logger.warning("nsfw_check_failed_allowing_upload")
                return (0.0, False)