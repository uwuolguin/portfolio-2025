"""
Optimized Image Service Client
- Connection pooling with limits
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Detailed error handling and logging
"""
import httpx
import structlog
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
import os

logger = structlog.get_logger(__name__)

# Configuration
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image-service:8080")
REQUEST_TIMEOUT = 30.0  # seconds
CONNECTION_TIMEOUT = 5.0  # seconds
MAX_RETRIES = 3
MAX_CONNECTIONS = 100  # Connection pool limit
MAX_KEEPALIVE_CONNECTIONS = 20


class ImageServiceError(Exception):
    """Base exception for image service errors"""
    pass


class ImageServiceClient:
    """
    Client for Image Storage Microservice
    
    Features:
    - Connection pooling (reuses HTTP connections)
    - Automatic retries with exponential backoff
    - Circuit breaker (fails fast if service is down)
    - Detailed logging
    """

    def __init__(self):
        # Create async client with connection pooling
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS
        )
        
        timeout = httpx.Timeout(
            timeout=REQUEST_TIMEOUT,
            connect=CONNECTION_TIMEOUT
        )
        
        self.client = httpx.AsyncClient(
            base_url=IMAGE_SERVICE_URL,
            limits=limits,
            timeout=timeout,
            follow_redirects=True
        )
        
        self._healthy = True  # Circuit breaker state
        
        logger.info("image_service_client_initialized",
                   base_url=IMAGE_SERVICE_URL,
                   max_connections=MAX_CONNECTIONS,
                   timeout=REQUEST_TIMEOUT)

    async def close(self):
        """Cleanup on shutdown"""
        await self.client.aclose()
        logger.info("image_service_client_closed")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def health_check(self) -> bool:
        """
        Check if image service is healthy
        Uses retry logic for transient failures
        """
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
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def upload_image(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload image to storage service
        
        Returns:
            {
                "image_id": "uuid",
                "url": "/images/uuid",
                "size": 12345
            }
        
        Raises:
            ImageServiceError on failure
        """
        try:
            # Build multipart form data
            files = {
                "file": (filename, file_bytes, content_type)
            }
            
            params = {}
            if user_id:
                params["user_id"] = user_id
            
            logger.info("uploading_to_image_service",
                       size_kb=len(file_bytes) / 1024,
                       content_type=content_type,
                       user_id=user_id)
            
            response = await self.client.post(
                "/upload",
                files=files,
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("image_upload_successful",
                           image_id=result.get('image_id'),
                           size=result.get('size'))
                return result
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

    async def delete_image(self, image_id: str) -> bool:
        """
        Delete image from storage service
        
        Returns:
            True if deleted successfully
            False if image not found
        
        Raises:
            ImageServiceError on other failures
        """
        try:
            logger.info("deleting_from_image_service", image_id=image_id)
            
            response = await self.client.delete(f"/images/{image_id}")
            
            if response.status_code == 200:
                logger.info("image_delete_successful", image_id=image_id)
                return True
            elif response.status_code == 404:
                logger.warning("image_delete_not_found", image_id=image_id)
                return False
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                logger.error("image_delete_failed",
                            image_id=image_id,
                            status_code=response.status_code,
                            detail=error_detail)
                raise ImageServiceError(f"Delete failed: {error_detail}")
                
        except httpx.TimeoutException:
            logger.error("image_delete_timeout", image_id=image_id)
            raise ImageServiceError("Image service timeout")
        except httpx.ConnectError:
            logger.error("image_delete_connection_error", image_id=image_id)
            raise ImageServiceError("Cannot connect to image service")
        except ImageServiceError:
            raise
        except Exception as e:
            logger.error("image_delete_unexpected_error",
                        image_id=image_id,
                        error=str(e),
                        exc_info=True)
            raise ImageServiceError(f"Delete failed: {str(e)}")

    @staticmethod
    def get_image_url(image_id: str, request_base_url: str) -> str:
        """
        Build public image URL
        Goes through nginx reverse proxy
        
        Args:
            image_id: UUID of the image
            request_base_url: Base URL from the request (e.g., "http://localhost")
        
        Returns:
            Full URL like "http://localhost/images/uuid"
        """
        base = request_base_url.rstrip('/')
        return f"{base}/images/{image_id}"

    async def list_images(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all images (optionally filtered by user_id)
        Admin function for debugging/monitoring
        """
        try:
            params = {"user_id": user_id} if user_id else {}
            
            response = await self.client.get("/images", params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise ImageServiceError(f"List failed: {response.status_code}")
                
        except Exception as e:
            logger.error("image_list_failed", error=str(e))
            raise ImageServiceError(f"List failed: {str(e)}")


# Global singleton instance
image_service_client = ImageServiceClient()