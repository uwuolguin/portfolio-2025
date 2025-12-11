"""
Image Service Client - Complete with helper methods
Handles all communication with the image storage microservice
"""
import httpx
import structlog
from typing import Optional, Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from typing import TypedDict
from app.config import settings
import logging

logger = structlog.get_logger(__name__)

class UploadedImage(TypedDict):
    image_id: str
    extension: str
    url: str
    size: int
    nsfw_score: float
    nsfw_checked: bool

class ImageServiceError(Exception):
    """Base exception for image service errors"""
    pass


class ImageServiceClient:
    """Client for Image Storage Microservice"""

    def __init__(self):
        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections
        )
        
        timeout = httpx.Timeout(
            timeout=settings.request_timeout,
            connect=settings.connection_timeout
        )
        
        self.client = httpx.AsyncClient(
            base_url=settings.image_service_url,
            limits=limits,
            timeout=timeout,
            follow_redirects=True
        )
        
        self._healthy = True
        
        logger.info("image_service_client_initialized",
                   base_url=settings.image_service_url,
                   max_connections=settings.max_connections,
                   timeout=settings.request_timeout)

    async def close(self):
        """Cleanup on shutdown"""
        await self.client.aclose()
        logger.info("image_service_client_closed")

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def health_check(self) -> bool:
        """Check if image service is healthy"""
        try:
            response = await self.client.get("/health", timeout=5.0)
            
            if response.status_code == 200:
                self._healthy = True
                logger.debug("image_service_health_ok")
                return True
            else:
                self._healthy = False
                logger.warning("image_service_health_degraded", 
                             status_code=response.status_code)
                return False
                
        except Exception as e:
            self._healthy = False
            logger.error("image_service_health_failed", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def upload_image(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        extension: str,
        user_id: Optional[str] = None
    ) -> UploadedImage:
        """
        Upload image to storage service
        
        Args:
            file_bytes: Image bytes
            filename: Company ID (used as base filename)
            content_type: MIME type
            extension: File extension (e.g., ".jpg", ".png")
            user_id: Optional user ID
        
        Returns:
            {
                "image_id": "uuid",
                "extension": ".jpg",
                "url": "/images/uuid.jpg",
                "size": 12345,
                "nsfw_score": 0.05,
                "nsfw_checked": true
            }
        
        Raises:
            ImageServiceError on failure
        """
        try:
            files = {
                "file": (f"{filename}{extension}", file_bytes, content_type)
            }
            
            data = {
                "company_id": filename,
                "extension": extension
            }
            
            if user_id:
                data["user_id"] = user_id
            
            logger.info("uploading_to_image_service",
                       size_kb=len(file_bytes) / 1024,
                       content_type=content_type,
                       extension=extension,
                       user_id=user_id)
            
            response = await self.client.post(
                "/upload",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("image_upload_successful",
                           image_id=result.get('image_id'),
                           extension=result.get('extension'),
                           size=result.get('size'))
                typed_result: UploadedImage = UploadedImage(
                    image_id=result['image_id'],
                    extension=result['extension'],
                    url=result['url'],
                    size=result['size'],
                    nsfw_score=result['nsfw_score'],
                    nsfw_checked=result['nsfw_checked']
                )
                return typed_result
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                logger.error("image_upload_failed",
                            status_code=response.status_code,
                            detail=error_detail)
                raise ImageServiceError(f"Upload failed: {error_detail}")
                
        except httpx.TimeoutException:
            logger.error("image_upload_timeout")
            raise ImageServiceError("Image service timeout")
        except httpx.ConnectError:
            logger.error("image_upload_connection_error")
            raise ImageServiceError("Cannot connect to image service")
        except Exception as e:
            logger.error("image_upload_unexpected_error", 
                        error=str(e), 
                        exc_info=True)
            raise ImageServiceError(f"Upload failed: {str(e)}")

    async def delete_image(self, filename: str) -> bool:
        """
        Delete image from storage service
        
        Args:
            filename: Full filename with extension (e.g., "uuid.jpg")
        
        Returns:
            True if deleted successfully
            False if image not found
        """
        try:
            logger.info("deleting_from_image_service", filename=filename)
            
            response = await self.client.delete(f"/images/{filename}")
            
            if response.status_code == 200:
                logger.info("image_delete_successful", filename=filename)
                return True
            elif response.status_code == 404:
                logger.warning("image_delete_not_found", filename=filename)
                return False
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                logger.error("image_delete_failed",
                            filename=filename,
                            status_code=response.status_code,
                            detail=error_detail)
                raise ImageServiceError(f"Delete failed: {error_detail}")
                
        except httpx.TimeoutException:
            logger.error("image_delete_timeout", filename=filename)
            raise ImageServiceError("Image service timeout")
        except httpx.ConnectError:
            logger.error("image_delete_connection_error", filename=filename)
            raise ImageServiceError("Cannot connect to image service")
        except ImageServiceError:
            raise
        except Exception as e:
            logger.error("image_delete_unexpected_error",
                        filename=filename,
                        error=str(e),
                        exc_info=True)
            raise ImageServiceError(f"Delete failed: {str(e)}")

    @staticmethod
    def get_extension_from_content_type(content_type: str) -> str:
        """
        Map content type to file extension
        
        Args:
            content_type: MIME type (e.g., "image/jpeg")
        
        Returns:
            File extension (e.g., ".jpg")
        
        Raises:
            ValueError: If content type is not supported
        """
        extension = settings.content_type_map.get(content_type)
        
        if not extension:
            raise ValueError(
                f"Unsupported image type: {content_type}. "
                f"Allowed: {', '.join(settings.content_type_map.keys())}"
            )
        
        return extension

    @staticmethod
    def build_image_url(image_id: str, extension: str, base_url: str) -> str:
        """
        Build public image URL
        Nginx proxies /images/* to image-service
        
        Args:
            image_id: Company UUID
            extension: File extension (e.g., ".jpg")
            base_url: Request base URL (e.g., "http://localhost")
        
        Returns:
            Full image URL (e.g., "http://localhost/images/uuid.jpg")
        """
        base = base_url.rstrip('/')
        return f"{base}/images/{image_id}{extension}"


image_service_client = ImageServiceClient()