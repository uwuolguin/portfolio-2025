import structlog
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import settings
from app.services.image_service_client import image_service_client

logger = structlog.get_logger(__name__)


class FileHandler:
    """
    Image operations delegated to Image Service
    All images stored in MinIO (no local files)
    """

    @staticmethod
    async def save_image(
        file: UploadFile,
        company_id: str
    ) -> Tuple[str, str]:
        """
        Upload image via Image Service
        
        Args:
            file: Uploaded file
            company_id: Company UUID (used as image filename)
            
        Returns:
            (image_id, extension) - e.g., ("uuid", ".jpg")
        """
        try:
            # Read file bytes
            file_bytes = await file.read()
            await file.seek(0)
            
            # Determine extension from content type
            extension = FileHandler.get_extension_from_content_type(file.content_type)
            
            logger.info(
                "uploading_to_image_service",
                size_kb=len(file_bytes) / 1024,
                content_type=file.content_type,
                extension=extension,
                company_id=company_id
            )
            
            # Upload to image service (which stores in MinIO)
            result = await image_service_client.upload_image(
                file_bytes=file_bytes,
                filename=company_id,
                content_type=file.content_type,
                extension=extension,
                user_id=company_id
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
    def get_extension_from_content_type(content_type: str) -> str:
        """Map content type to file extension"""
        extension = settings.content_type_map.get(content_type)
        
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image type: {content_type}"
            )
        
        return extension

    @staticmethod
    async def delete_image(image_id: str, extension: str) -> bool:
        """Delete image via Image Service"""
        filename = f"{image_id}{extension}"
        return await image_service_client.delete_image(filename)
    
    @staticmethod
    def get_image_url(image_id: str, extension: str, request_base_url: str) -> str:
        """
        Build public image URL
        Nginx proxies /images/* to image-service
        """
        base = request_base_url.rstrip('/')
        return f"{base}/images/{image_id}{extension}"
    
    @staticmethod
    def get_nsfw_status() -> dict:
        """Not used anymore - image-service handles this"""
        return {"message": "NSFW checking handled by image-service"}