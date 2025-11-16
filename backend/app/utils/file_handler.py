"""
Simplified File Handler
- Delegates all image processing to Image Service
- No NSFW detection (handled by image service)
- Just sends files to image service and handles responses
"""
import structlog
from typing import Optional

from fastapi import UploadFile, HTTPException, status
from app.config import settings
from app.utils.image_service_client import image_service_client

logger = structlog.get_logger(__name__)


class FileHandler:
    """
    Simplified file handler that delegates to Image Service
    
    All image validation, processing, and NSFW detection happens in the image service.
    This class just coordinates the upload/delete operations.
    """

    @staticmethod
    async def save_image(
        file: UploadFile,
        company_id: str
    ) -> str:
        """
        Upload image to Image Service
        
        The image service will:
        - Validate format (JPEG/PNG/WebP)
        - Check file size (<10MB)
        - Optimize image
        - Detect NSFW content
        - Store in MinIO
        
        Args:
            file: UploadFile from FastAPI
            company_id: UUID of the company (used as filename)
        
        Returns:
            image_id: Same as company_id (for backward compatibility)
        
        Raises:
            HTTPException: If upload fails or validation fails
        """
        try:
            # Read file bytes
            file_bytes = await file.read()
            await file.seek(0)  # Reset for potential re-reads
            
            logger.info("uploading_to_image_service",
                       size_kb=len(file_bytes) / 1024,
                       content_type=file.content_type,
                       company_id=company_id)
            
            # Upload to image service (validates, checks NSFW, stores)
            result = await image_service_client.upload_image(
                file_bytes=file_bytes,
                filename=f"{company_id}.jpg",  # Extension will be determined by service
                content_type=file.content_type or "image/jpeg",
                user_id=company_id
            )
            
            logger.info(
                "image_saved_successfully",
                image_id=result['image_id'],
                size=result['size'],
                nsfw_checked=result.get('nsfw_checked', False),
                nsfw_score=result.get('nsfw_score')
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
        
        Args:
            image_id: ID of the image to delete (company_id)
        
        Returns:
            True if deleted, False if not found
        """
        return await image_service_client.delete_image(image_id)
    
    @staticmethod
    def get_image_url(image_id: str, request_base_url: str) -> str:
        """
        Convert image_id to public URL
        Goes through nginx reverse proxy to image service
        
        Args:
            image_id: ID of the image (company_id)
            request_base_url: Base URL from the request
        
        Returns:
            Full URL like "http://localhost/images/uuid"
        """
        return image_service_client.get_image_url(image_id, request_base_url)