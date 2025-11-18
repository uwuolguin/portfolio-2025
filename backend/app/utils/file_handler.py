"""
Simplified File Handler
- Delegates all image processing to Image Service
- Determines extension from uploaded file BEFORE sending
"""
import structlog
from typing import Tuple
import os

from fastapi import UploadFile, HTTPException, status
from app.config import settings
from app.utils.image_service_client import image_service_client

logger = structlog.get_logger(__name__)


class FileHandler:
    """
    File handler that delegates to Image Service
    
    Key change: Determines extension from uploaded file BEFORE sending to image service
    """

    @staticmethod
    def get_extension_from_content_type(content_type: str) -> str:
        """
        Map content type to file extension
        
        Args:
            content_type: MIME type (e.g., "image/jpeg")
            
        Returns:
            Extension with dot (e.g., ".jpg")
            
        Raises:
            HTTPException if content type is invalid
        """
        
        extension = settings.content_type_map.get(content_type)
        
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image type: {content_type}. Allowed: {list(settings.content_type_map.keys())}"
            )
        
        return extension

    @staticmethod
    async def save_image(
        file: UploadFile,
        company_id: str
    ) -> Tuple[str, str]:
        """
        Upload image to Image Service
        
        Flow:
        1. Determine extension from content type
        2. Upload to image service with extension
        3. Return image_id and extension
        
        Args:
            file: Uploaded file
            company_id: Company UUID (used as image ID)
            
        Returns:
            Tuple of (image_id, extension) - e.g., ("uuid", ".jpg")
        
        Raises:
            HTTPException: If upload fails or validation fails
        """
        try:
            file_bytes = await file.read()
            await file.seek(0)
            
            extension = FileHandler.get_extension_from_content_type(file.content_type)
            
            logger.info(
                "uploading_to_image_service",
                size_kb=len(file_bytes) / 1024,
                content_type=file.content_type,
                extension=extension,
                company_id=company_id
            )
            
            result = await image_service_client.upload_image(
                file_bytes=file_bytes,
                filename=company_id, 
                content_type=file.content_type,
                extension=extension,
                user_id=company_id
            )
            
            returned_extension = result.get('extension')
            if returned_extension != extension:
                logger.error(
                    "extension_mismatch",
                    sent=extension,
                    returned=returned_extension
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Image service returned unexpected extension"
                )
            
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
    async def delete_image(image_id: str, extension: str) -> bool:
        """
        Delete an image via Image Service
        
        Args:
            image_id: ID of the image to delete (company_id)
            extension: File extension (e.g., ".jpg")
        
        Returns:
            True if deleted, False if not found
        """
        filename = f"{image_id}{extension}"
        return await image_service_client.delete_image(filename)
    
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