"""
Simplified File Handler
- Delegates all image processing to Image Service
- No NSFW detection (handled by image service)
- Just sends files to image service and handles responses
"""
import structlog
from typing import Optional,Tuple

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
    ) -> Tuple[str, str]:
        """
        Upload image to Image Service
        
        Returns:
            Tuple of (image_id, extension) - e.g., ("uuid", ".jpg")
        
        Raises:
            HTTPException: If upload fails or validation fails
        """
        try:
            file_bytes = await file.read()
            await file.seek(0)
            
            logger.info("uploading_to_image_service",
                    size_kb=len(file_bytes) / 1024,
                    content_type=file.content_type,
                    company_id=company_id)
            
            result = await image_service_client.upload_image(
                file_bytes=file_bytes,
                filename=company_id, 
                content_type=file.content_type ,
                user_id=company_id
            )
            
            extension = result.get('extension')
            
            logger.info(
                "image_saved_successfully",
                image_id=result['image_id'],
                extension=extension,
                size=result['size']
            )
            
            return result['image_id'], extension

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
    def get_image_url(image_id: str, extension: str, request_base_url: str) -> str:
        """
        Build public image URL with extension
        
        Args:
            image_id: UUID of the image
            extension: File extension (e.g., ".jpg")
            request_base_url: Base URL from request
        
        Returns:
            Full URL like "http://localhost/images/uuid.jpg"
        """
        base = request_base_url.rstrip('/')
        return f"{base}/images/{image_id}{extension}"