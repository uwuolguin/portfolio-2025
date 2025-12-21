"""
Image Validation and NSFW Detection Module
Handles image processing, optimization, and content moderation

OPTIMIZED VERSION:
- Accepts file-like objects (BytesIO) consistently
- Minimizes memory copies
- Clear type hints
- Returns BytesIO for efficient streaming
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
        image_stream: BytesIO,
        content_type: str,
        extension: str
    ) -> BytesIO:
        """
        Validate and process an image from a file-like stream.
        
        Args:
            image_stream: BytesIO object containing image data (size pre-validated)
            content_type: MIME type (e.g., "image/jpeg")
            extension: File extension (e.g., ".jpg", ".png")
            
        Returns:
            BytesIO: Processed and optimized image stream
            
        Raises:
            ValueError: If validation fails
            
        Note:
            Size validation is handled by main.py during streaming upload.
            This function focuses on format, dimensions, and optimization.
        """
        if content_type not in settings.allowed_types:
            raise ValueError(
                f"Unsupported MIME type: {content_type}. "
                f"Allowed: {', '.join(sorted(settings.allowed_types))}"
            )
        
        image_stream.seek(0)

        try:
            with Image.open(image_stream) as img:
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
            if img_copy.mode == "P)":
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
        processed_size = out.getbuffer().nbytes
        logger.info(
            "image_validated_and_processed",
            format=expected_format,
            extension=extension,
            processed_size_kb=processed_size / 1024,
            dimensions=f"{img_copy.width}x{img_copy.height}",
        )

        return out

    @classmethod
    def check_nsfw_content(cls, image_stream: BytesIO) -> Tuple[float, bool]:
        """
        Check if image contains NSFW content.
        
        Args:
            image_stream: BytesIO object containing image data
            
        Returns:
            Tuple[float, bool]: (nsfw_score, check_performed)
                - nsfw_score: 0.0-1.0, higher = more NSFW
                - check_performed: True if model ran, False if failed/disabled
                
        Memory efficiency:
            - Reuses input stream (no copy)
            - OpenNSFW2 loads into memory (unavoidable)
            - Stream is rewound after check
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
            image_stream.seek(0)
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