"""
Image Service Client
Handles communication with the image storage microservice

OPTIMIZED VERSION:
- Streams files directly without intermediate buffering
- Minimal memory footprint
- Clear error handling
- Type-safe responses
"""

from typing import Optional, TypedDict, Final
import httpx
import structlog
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import settings

logger = structlog.get_logger(__name__)


class UploadedImage(TypedDict):
    """Type definition for uploaded image response"""
    image_id: str
    extension: str
    url: str
    size: int
    nsfw_score: Optional[float]
    nsfw_checked: bool


class ImageServiceError(Exception):
    """Base exception for image service errors"""
    pass


_RETRY_POLICY: Final = retry(
    stop=stop_after_attempt(settings.max_retries),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (httpx.ConnectError, httpx.TimeoutException)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class ImageServiceClient:
    """
    Async client for Image Storage Microservice
    
    Features:
    - Streaming uploads to minimize memory usage
    - Automatic retries with exponential backoff
    - Connection pooling and keepalive
    - Structured logging with correlation
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        """
        Initialize the image service client.
        
        Args:
            client: Optional pre-configured httpx client. If not provided,
                   creates a new client with connection pooling.
        """
        if client is not None:
            self._client = client
            return

        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        )

        timeout = httpx.Timeout(
            timeout=settings.request_timeout,
            connect=settings.connection_timeout,
        )

        self._client = httpx.AsyncClient(
            base_url=settings.image_service_url,
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
        )

        logger.info(
            "image_service_client_initialized",
            base_url=settings.image_service_url,
            max_connections=settings.max_connections,
            timeout=settings.request_timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources"""
        await self._client.aclose()
        logger.info("image_service_client_closed")

    @staticmethod
    def _raise_for_error(response: httpx.Response, action: str) -> None:
        """
        Check response status and raise ImageServiceError if not successful.
        
        Args:
            response: HTTP response object
            action: Description of the action being performed
            
        Raises:
            ImageServiceError: If response status is not 200/201
        """
        if response.status_code in (200, 201):
            return

        try:
            detail = response.json().get("detail", "Unknown error")
        except Exception:
            detail = response.text

        logger.error(
            action,
            status_code=response.status_code,
            detail=detail,
        )
        raise ImageServiceError(f"{action}: {detail}")

    @_RETRY_POLICY
    async def health_check(self) -> bool:
        """
        Check if image service is healthy.
        
        Returns:
            bool: True if service is healthy
            
        Raises:
            httpx exceptions on connection failures
        """
        response = await self._client.get("/health", timeout=5.0)
        return response.status_code == 200

    @_RETRY_POLICY
    async def upload_image_streaming(
        self,
        file_obj,
        company_id: str,
        content_type: str,
        extension: str,
        user_id: Optional[str] = None,
    ) -> UploadedImage:
        """
        Upload image using streaming to minimize memory usage.
        
        RECOMMENDED METHOD: Streams file directly from FastAPI's UploadFile
        to the image service without intermediate buffering.
        
        Args:
            file_obj: File-like object (SpooledTemporaryFile from FastAPI)
            company_id: UUID of the company (used as base filename)
            content_type: MIME type (e.g., "image/jpeg")
            extension: File extension (e.g., ".jpg", ".png")
            user_id: Optional user UUID for audit logging
            
        Returns:
            UploadedImage dict containing:
                - image_id: Company UUID
                - extension: File extension
                - url: Relative URL to access image
                - size: File size in bytes
                - nsfw_score: NSFW detection score (0.0-1.0) or None
                - nsfw_checked: Whether NSFW check was performed
                
        Raises:
            ImageServiceError: On upload failure or validation error
            httpx exceptions: On network/connection failures
            
        Memory usage: Minimal - file streams through without buffering
            
        Example:
            >>> async with open('image.jpg', 'rb') as f:
            ...     result = await client.upload_image_streaming(
            ...         file_obj=f,
            ...         company_id="550e8400-e29b-41d4-a716-446655440001",
            ...         content_type="image/jpeg",
            ...         extension=".jpg"
            ...     )
            >>> print(result['url'])
            /images/550e8400-e29b-41d4-a716-446655440001.jpg
        """
        
        files = {
            "file": (f"{company_id}{extension}", file_obj, content_type)
        }

        data = {
            "company_id": company_id,
            "extension": extension,
        }

        if user_id:
            data["user_id"] = user_id

        logger.info(
            "uploading_to_image_service_streaming",
            company_id=company_id,
            content_type=content_type,
            extension=extension,
            user_id=user_id,
        )

        response = await self._client.post("/upload", files=files, data=data)
        self._raise_for_error(response, "image_upload_failed")

        result = response.json()

        logger.info(
            "image_upload_successful",
            image_id=result["image_id"],
            extension=result["extension"],
            size=result["size"],
            nsfw_checked=result["nsfw_checked"],
            nsfw_score=result.get("nsfw_score"),
        )

        return {
            "image_id": result["image_id"],
            "extension": result["extension"],
            "url": result["url"],
            "size": result["size"],
            "nsfw_score": result.get("nsfw_score"),
            "nsfw_checked": result["nsfw_checked"],
        }

    async def delete_image(self, filename: str) -> bool:
        """
        Delete an image from storage.
        
        Args:
            filename: Complete filename including extension
                     (e.g., "550e8400-e29b-41d4-a716-446655440001.jpg")
                     
        Returns:
            bool: True if deleted, False if not found
            
        Raises:
            ImageServiceError: On deletion failure (other than 404)
            
        Example:
            >>> success = await client.delete_image(
            ...     "550e8400-e29b-41d4-a716-446655440001.jpg"
            ... )
            >>> if success:
            ...     print("Image deleted successfully")
        """
        logger.info("deleting_from_image_service", filename=filename)

        response = await self._client.delete(f"/images/{filename}")

        if response.status_code == 200:
            logger.info("image_delete_successful", filename=filename)
            return True

        if response.status_code == 404:
            logger.warning("image_delete_not_found", filename=filename)
            return False

        self._raise_for_error(response, "image_delete_failed")
        return False

    @staticmethod
    def get_extension_from_content_type(content_type: str) -> str:
        """
        Map MIME type to file extension.
        
        Args:
            content_type: MIME type (e.g., "image/jpeg")
            
        Returns:
            str: File extension (e.g., ".jpg")
            
        Raises:
            ValueError: If content type is not supported
            
        Example:
            >>> ext = ImageServiceClient.get_extension_from_content_type("image/jpeg")
            >>> print(ext)
            .jpg
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
        Build full URL for accessing an image.
        
        Args:
            image_id: Company UUID (base filename)
            extension: File extension including dot (e.g., ".jpg")
            base_url: Base URL of the application
            
        Returns:
            str: Complete URL to access the image
            
        Example:
            >>> url = ImageServiceClient.build_image_url(
            ...     "550e8400-e29b-41d4-a716-446655440001",
            ...     ".jpg",
            ...     "http://localhost"
            ... )
            >>> print(url)
            http://localhost/images/550e8400-e29b-41d4-a716-446655440001.jpg
        """
        base = base_url.rstrip("/")
        return f"{base}/images/{image_id}{extension}"


image_service_client = ImageServiceClient()