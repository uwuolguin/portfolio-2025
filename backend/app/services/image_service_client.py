"""
Image Service Client
Handles communication with the image storage microservice

OPTIMIZED VERSION:
- Streams files directly without intermediate buffering
- Minimal memory footprint
- Clear error handling
- Type-safe responses
"""

import logging
from typing import Optional, TypedDict, Final
import httpx
import structlog

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import settings
from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
)

logger = structlog.get_logger(__name__)


class UploadedImage(TypedDict):
    """Type definition for uploaded image response."""

    image_id: str
    extension: str
    url: str
    size: int
    nsfw_score: Optional[float]
    nsfw_checked: bool


class ImageServiceError(Exception):
    """Exception raised for image service errors."""


_RETRY_POLICY: Final = retry(
    stop=stop_after_attempt(settings.max_retries),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
)


class ImageServiceClient:
    """
    Async client for Image Storage Microservice
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
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
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("image_service_client_closed")

    @staticmethod
    def _raise_for_error(
        response: httpx.Response, action: str
    ) -> None:  # pylint: disable=missing-function-docstring
        if response.status_code in (200, 201):
            return

        try:
            detail = response.json().get("detail", "Unknown error")
        except Exception:  # pylint: disable=broad-exception-caught
            detail = response.text

        logger.error(
            action,
            status_code=response.status_code,
            detail=detail,
        )
        raise ImageServiceError(f"{action}: {detail}")

    @_RETRY_POLICY
    async def _upload_request(
        self,
        file_obj,
        company_id: str,
        content_type: str,
        extension: str,
    ) -> httpx.Response:
        files = {
            "file": (f"{company_id}{extension}", file_obj, content_type),
        }

        data = {
            "company_id": company_id,
            "extension": extension,
        }

        return await self._client.post(
            "/upload",
            files=files,
            data=data,
        )

    async def upload_image_streaming(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        file_obj,
        company_id: str,
        content_type: str,
        extension: str,
        user_id: Optional[str] = None,  # pylint: disable=unused-argument
    ) -> UploadedImage:
        """Upload an image using streaming to minimize memory usage."""
        await _circuit_breaker.allow_call()

        try:
            response = await self._upload_request(
                file_obj=file_obj,
                company_id=company_id,
                content_type=content_type,
                extension=extension,
            )

            if response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    "Image service error",
                    request=response.request,
                    response=response,
                )

            self._raise_for_error(response, "image_upload_failed")

            result = response.json()
            await _circuit_breaker.record_success()

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

        except CircuitBreakerOpen:
            # Re-raise immediately - no cleanup needed
            raise

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            await _circuit_breaker.record_failure()
            raise

        except ImageServiceError:
            # Re-raise immediately - no cleanup needed
            raise

    async def delete_image(
        self, filename: str
    ) -> bool:  # pylint: disable=missing-function-docstring
        """Delete an image from the storage service."""
        await _circuit_breaker.allow_call()

        try:
            response = await self._client.delete(f"/images/{filename}")

            if response.status_code == 200:
                await _circuit_breaker.record_success()
                return True

            if response.status_code == 404:
                await _circuit_breaker.record_success()
                return False

            if response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    "Image service error",
                    request=response.request,
                    response=response,
                )

            self._raise_for_error(response, "image_delete_failed")
            await _circuit_breaker.record_success()
            return False

        except CircuitBreakerOpen:
            # Re-raise immediately - no cleanup needed
            raise

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            await _circuit_breaker.record_failure()
            raise

    @staticmethod
    def get_extension_from_content_type(
        content_type: str,
    ) -> str:  # pylint: disable=missing-function-docstring
        """Get file extension from content type using settings mapping."""
        extension = settings.content_type_map.get(content_type)  # type: ignore
        if not extension:
            raise ValueError(
                f"Unsupported image type: {content_type}. "
                f"Allowed: {', '.join(settings.content_type_map.keys())}"  # type: ignore
            )
        return extension

    @staticmethod
    def build_image_url(
        image_id: str, extension: str
    ) -> str:  # pylint: disable=missing-function-docstring
        """Build the full URL for an image."""
        base = settings.api_base_url.rstrip("/")
        return f"{base}/images/{image_id}{extension}"


image_service_client = ImageServiceClient()
