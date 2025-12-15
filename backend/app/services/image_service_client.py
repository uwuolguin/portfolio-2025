"""
Image Service Client
Handles communication with the image storage microservice
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
    image_id: str
    extension: str
    url: str
    size: int
    nsfw_score: Optional[float]
    nsfw_checked: bool

class ImageServiceError(Exception):
    """Base exception for image service errors"""

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
    """Async client for Image Storage Microservice"""

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
        await self._client.aclose()
        logger.info("image_service_client_closed")

    @staticmethod
    def _raise_for_error(response: httpx.Response, action: str) -> None:
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
        response = await self._client.get("/health", timeout=5.0)
        return response.status_code == 200

    @_RETRY_POLICY
    async def upload_image(
        self,
        file_bytes: bytes,
        company_id: str,
        content_type: str,
        extension: str,
        user_id: Optional[str] = None,
    ) -> UploadedImage:

        files = {
            "file": (f"{company_id}{extension}", file_bytes, content_type)
        }

        data = {
            "company_id": company_id,
            "extension": extension,
        }

        if user_id:
            data["user_id"] = user_id

        logger.info(
            "uploading_to_image_service",
            company_id=company_id,
            size_kb=len(file_bytes) / 1024,
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
        extension = settings.content_type_map.get(content_type)
        if not extension:
            raise ValueError(
                f"Unsupported image type: {content_type}. "
                f"Allowed: {', '.join(settings.content_type_map.keys())}"
            )
        return extension

    @staticmethod
    def build_image_url(image_id: str, extension: str, base_url: str) -> str:
        base = base_url.rstrip("/")
        return f"{base}/images/{image_id}{extension}"


image_service_client = ImageServiceClient()
