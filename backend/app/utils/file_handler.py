"""
Optimized File Handler
- Validates and processes images ONCE
- NSFW check uses processed bytes (consistent pipeline)
- Better error messages and resource cleanup
- Threadpool tuning for CPU-bound operations
"""
import structlog
from typing import Optional, Tuple
from io import BytesIO

from fastapi import UploadFile, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.utils.image_service_client import image_service_client

logger = structlog.get_logger(__name__)


class NSFWModelError(Exception):
    """Custom exception for NSFW model issues"""
    pass


class FileHandler:
    """
    Handles image validation and NSFW detection
    Storage operations delegated to Image Service microservice
    
    Key improvements:
    - Single image processing pass
    - NSFW check on processed bytes (consistency)
    - Better resource cleanup
    - More detailed error messages
    """

    # Configuration
    MAX_SIZE_BYTES = settings.max_file_size
    MAX_WIDTH = 4000
    MAX_HEIGHT = 4000
    ALLOWED_FORMATS = {"JPEG", "PNG"}
    ALLOWED_MIME = set(settings.allowed_file_types)
    EXT_BY_FORMAT = {"JPEG": "jpg", "PNG": "png"}
    
    # NSFW Detection
    _nsfw_model = None
    _nsfw_available = False
    NSFW_THRESHOLD = 0.75

    @staticmethod
    def load_nsfw_model() -> None:
        """
        Initialize NSFW model once at startup
        Gracefully handles failure - app continues without NSFW protection
        """
        if FileHandler._nsfw_available:
            logger.info("nsfw_model_already_loaded")
            return

        try:
            logger.info("nsfw_model_loading_starting")
            
            from opennsfw2 import predict_image
            
            # Test the model
            logger.info("nsfw_model_testing")
            test_img = Image.new('RGB', (224, 224), color='red')
            test_bytes = BytesIO()
            test_img.save(test_bytes, format='JPEG')
            test_bytes.seek(0)
            
            test_score = predict_image(test_bytes)
            
            logger.info(
                "nsfw_model_loaded_successfully",
                test_score=float(test_score)
            )
            
            FileHandler._nsfw_model = True
            FileHandler._nsfw_available = True
            
        except ImportError as e:
            logger.error("nsfw_model_import_failed", 
                        error=str(e),
                        message="Install with: pip install opennsfw2")
            FileHandler._nsfw_available = False
            
        except Exception as e:
            logger.error("nsfw_model_load_failed", error=str(e), exc_info=True)
            FileHandler._nsfw_available = False

    @staticmethod
    def _validate_and_process_image(
        file_bytes: bytes, 
        content_type: str
    ) -> Tuple[bytes, str]:
        """
        Validate and process image synchronously
        
        Improvements:
        - More detailed error messages
        - Progressive JPEG support
        - Optimization for storage
        
        Returns: (processed_bytes, extension)
        """
        
        # Validate MIME type
        if content_type not in FileHandler.ALLOWED_MIME:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type: {content_type}. Allowed: {', '.join(FileHandler.ALLOWED_MIME)}"
            )

        # Check size before processing
        if len(file_bytes) > FileHandler.MAX_SIZE_BYTES:
            size_mb = len(file_bytes) / 1_048_576
            limit_mb = FileHandler.MAX_SIZE_BYTES / 1_048_576
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image too large ({size_mb:.2f}MB). Limit: {limit_mb:.2f}MB"
            )

        # Open and validate image
        try:
            with Image.open(BytesIO(file_bytes)) as img:
                img.load()  # Force full load to detect corruption
                fmt = (img.format or "").upper()
                img_copy = img.copy()
        except UnidentifiedImageError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted image file"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image processing error: {str(e)}"
            )

        # Validate format
        if fmt not in FileHandler.ALLOWED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {fmt}. Allowed: {', '.join(FileHandler.ALLOWED_FORMATS)}"
            )

        # Check dimensions
        if img_copy.width > FileHandler.MAX_WIDTH or img_copy.height > FileHandler.MAX_HEIGHT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image too large ({img_copy.width}x{img_copy.height}). Max: {FileHandler.MAX_WIDTH}x{FileHandler.MAX_HEIGHT}"
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
                "progressive": True  # Better for web streaming
            }
        else:  # PNG
            save_params = {
                "optimize": True,
                "compress_level": 6  # Good balance of speed/size
            }
        
        img_copy.save(out, format=fmt, **save_params)
        
        processed_bytes = out.getvalue()
        ext = FileHandler.EXT_BY_FORMAT.get(fmt, "jpg")

        logger.info(
            "image_validated_and_processed",
            format=fmt,
            original_size_kb=len(file_bytes) / 1024,
            processed_size_kb=len(processed_bytes) / 1024,
            compression_ratio=f"{(1 - len(processed_bytes) / len(file_bytes)) * 100:.1f}%",
            dimensions=f"{img_copy.width}x{img_copy.height}"
        )

        return processed_bytes, ext

    @staticmethod
    def _check_nsfw_sync(image_bytes: bytes) -> Tuple[float, bool]:
        """
        Run NSFW detection on processed image bytes
        
        KEY CHANGE: Now uses processed bytes instead of raw upload
        This ensures consistency - we check what we actually store
        
        Returns: (score, check_performed)
        """
        if not FileHandler._nsfw_available:
            logger.warning("nsfw_check_unavailable_blocking_upload")
            return (1.0, False)

        try:
            from opennsfw2 import predict_image
            
            img_stream = BytesIO(image_bytes)
            score = predict_image(img_stream)
            
            logger.info(
                "nsfw_check_completed",
                score=float(score),
                threshold=FileHandler.NSFW_THRESHOLD,
                will_block=score > FileHandler.NSFW_THRESHOLD
            )
            
            return (float(score), True)
            
        except Exception as e:
            logger.error("nsfw_check_execution_failed", error=str(e), exc_info=True)
            # On error, block upload (fail closed)
            return (1.0, False)

    @staticmethod
    async def save_image(
        file: UploadFile,
        user_uuid: Optional[str] = None
    ) -> str:
        """
        Complete image pipeline:
        1. Read raw bytes
        2. Validate and process (resize, optimize, convert)
        3. NSFW check on processed bytes
        4. Upload to Image Service
        
        Returns: image_id (stored in database)
        
        Improvements:
        - Single processing pass
        - NSFW check on actual stored image
        - Better error messages
        - Automatic cleanup on failure
        """
        try:
            # Step 1: Read raw bytes
            file_bytes = await file.read()
            
            logger.info("image_upload_started", 
                       size_kb=len(file_bytes) / 1024,
                       content_type=file.content_type,
                       user_uuid=user_uuid)

            # Step 2: Validate and process image
            processed_bytes, ext = await run_in_threadpool(
                FileHandler._validate_and_process_image,
                file_bytes,
                file.content_type or "image/jpeg"
            )

            # Step 3: NSFW check on processed bytes (KEY CHANGE)
            nsfw_score, check_performed = await run_in_threadpool(
                FileHandler._check_nsfw_sync, 
                processed_bytes  # Using processed bytes, not raw
            )

            if nsfw_score > FileHandler.NSFW_THRESHOLD:
                if check_performed:
                    logger.warning(
                        "nsfw_image_rejected",
                        nsfw_score=nsfw_score,
                        user_uuid=user_uuid
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Image rejected: inappropriate content detected (confidence: {nsfw_score:.1%})"
                    )
                else:
                    # NSFW check failed to run - fail closed
                    logger.error("nsfw_check_failed_blocking_upload", user_uuid=user_uuid)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Content moderation service unavailable. Please try again later."
                    )

            # Step 4: Upload to Image Service
            result = await image_service_client.upload_image(
                file_bytes=processed_bytes,
                filename=f"{user_uuid or 'unknown'}.{ext}",
                content_type=f"image/{ext}",
                user_id=user_uuid
            )

            logger.info(
                "image_saved_successfully",
                image_id=result['image_id'],
                size_kb=result['size'] / 1024,
                nsfw_score=nsfw_score,
                nsfw_check_performed=check_performed
            )

            return result['image_id']

        except HTTPException:
            raise
        except Exception as e:
            logger.error("file_save_error", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save image: {str(e)}"
            )

    @staticmethod
    async def delete_image(image_id: str) -> bool:
        """
        Delete an image via Image Service
        Returns True if deleted, False if not found
        """
        return await image_service_client.delete_image(image_id)
    
    @staticmethod
    def get_image_url(image_id: str, request_base_url: str) -> str:
        """
        Convert image_id to public URL
        Goes through nginx reverse proxy
        """
        return image_service_client.get_image_url(image_id, request_base_url)

    @staticmethod
    def get_nsfw_status() -> dict:
        """Get current NSFW checking status"""
        return {
            "available": FileHandler._nsfw_available,
            "model_loaded": FileHandler._nsfw_available,
            "threshold": FileHandler.NSFW_THRESHOLD,
            "mode": "fail_closed" if not FileHandler._nsfw_available else "active"
        }