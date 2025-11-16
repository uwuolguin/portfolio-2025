from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional
from minio import Minio
from minio.error import S3Error
import structlog
import os
from contextlib import asynccontextmanager

from config import settings

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if not await run_in_threadpool(minio_client.bucket_exists, settings.minio_bucket):
            await run_in_threadpool(minio_client.make_bucket, settings.minio_bucket)
            logger.info("bucket_created", bucket=settings.minio_bucket)
        else:
            logger.info("bucket_exists", bucket=settings.minio_bucket)

        logger.info(
            "image_service_started",
            endpoint=settings.minio_endpoint,
            bucket=settings.minio_bucket,
            max_file_size_mb=settings.max_file_size / 1_000_000,
        )
    except Exception as e:
        logger.error("startup_failed", error=str(e), exc_info=True)
        raise

    yield

    logger.info("image_service_shutdown")


app = FastAPI(
    title=settings.service_name,
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def build_object_name(company_id: str, ext: str) -> str:
    """
    Build MinIO object path using ONLY company_id
    Format: {company_id}.{ext}
    Example: 550e8400-e29b-41d4-a716-446655440001.jpg
    """
    return f"{company_id}{ext}"


async def find_object_by_id(company_id: str) -> Optional[str]:
    """
    Find object in MinIO by company_id (searches all extensions)
    """
    try:
        objects = await run_in_threadpool(
            lambda: list(minio_client.list_objects(settings.minio_bucket, recursive=True))
        )

        # Search for company_id with any extension
        suffixes = (f"{company_id}.jpg", f"{company_id}.png", f"{company_id}.webp")

        for obj in objects:
            if obj.object_name in suffixes:
                return obj.object_name

        return None
    except S3Error as e:
        logger.error("find_object_failed", company_id=company_id, error=str(e))
        return None


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        await run_in_threadpool(minio_client.bucket_exists, settings.minio_bucket)
        return {
            "status": "healthy",
            "service": "image-storage",
            "bucket": settings.minio_bucket,
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MinIO connection failed",
        )


@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    company_id: str = None,  # CHANGED: now company_id instead of user_id
):
    """
    Upload an image to MinIO using company_id as filename
    Returns: company_id (as image_id for backward compatibility), url, size
    """
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required"
        )
    
    # Validate content type
    ctype = file.content_type
    if ctype not in settings.allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ctype}",
        )

    spooled = file.file

    try:
        # Check file size
        await run_in_threadpool(spooled.seek, 0, os.SEEK_END)
        size = await run_in_threadpool(spooled.tell)
        await run_in_threadpool(spooled.seek, 0)

        if size > settings.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max {settings.max_file_size / 1_000_000}MB",
            )

        # Determine extension
        ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[ctype]

        # Build object name using ONLY company_id
        object_name = build_object_name(company_id, ext)
        
        # Delete old image if exists (different extension)
        for old_ext in [".jpg", ".png", ".webp"]:
            if old_ext != ext:
                old_object_name = build_object_name(company_id, old_ext)
                try:
                    await run_in_threadpool(
                        minio_client.remove_object,
                        settings.minio_bucket,
                        old_object_name
                    )
                    logger.info("old_image_deleted", object_name=old_object_name)
                except:
                    pass  # Old image doesn't exist, that's fine

        # Upload to MinIO
        await run_in_threadpool(
            minio_client.put_object,
            settings.minio_bucket,
            object_name,
            spooled,
            length=size,
            content_type=ctype,
        )

        logger.info(
            "upload_success",
            company_id=company_id,
            size=size,
            object_name=object_name,
        )

        return {
            "image_id": company_id,  # Return company_id as image_id
            "url": f"/images/{company_id}",
            "size": size,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )
    finally:
        try:
            await run_in_threadpool(spooled.close)
        except Exception:
            pass


@app.get("/images/{company_id}")
async def get_image(company_id: str):
    """
    Stream an image from MinIO using company_id
    Efficient for large files - uses chunked streaming
    """
    # Find the object by company_id
    object_name = await find_object_by_id(company_id)

    if not object_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    try:
        # Get object metadata
        try:
            stat = await run_in_threadpool(
                minio_client.stat_object, settings.minio_bucket, object_name
            )
            length = stat.size
            ctype = stat.content_type or "application/octet-stream"
        except Exception:
            length = None
            ctype = "application/octet-stream"

        # Get object stream
        obj = await run_in_threadpool(
            minio_client.get_object, settings.minio_bucket, object_name
        )

        # Stream generator
        async def stream_generator():
            try:
                while True:
                    chunk = await run_in_threadpool(obj.read, settings.chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    await run_in_threadpool(obj.close)
                except Exception:
                    pass
                try:
                    await run_in_threadpool(obj.release_conn)
                except Exception:
                    pass

        headers = {
            "Cache-Control": "public, max-age=2592000",  # 30 days
            "Content-Disposition": f'inline; filename="{company_id}"',
        }

        if length is not None:
            headers["Content-Length"] = str(length)

        return StreamingResponse(
            stream_generator(),
            media_type=ctype,
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_image_failed",
            company_id=company_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retrieval failed",
        )


@app.delete("/images/{company_id}")
async def delete_image(company_id: str):
    """Delete an image from MinIO using company_id"""
    object_name = await find_object_by_id(company_id)

    if not object_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    try:
        await run_in_threadpool(
            minio_client.remove_object, settings.minio_bucket, object_name
        )

        logger.info("delete_success", company_id=company_id, object_name=object_name)

        return {
            "status": "deleted",
            "image_id": company_id,
        }

    except Exception as e:
        logger.error(
            "delete_failed",
            company_id=company_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )


@app.get("/images")
async def list_images():
    """List all images in the bucket"""
    try:
        objects = await run_in_threadpool(
            lambda: list(
                minio_client.list_objects(
                    settings.minio_bucket,
                    recursive=True,
                )
            )
        )

        return {
            "count": len(objects),
            "objects": [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat()
                    if obj.last_modified
                    else None,
                }
                for obj in objects
            ],
        }

    except Exception as e:
        logger.error("list_images_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list images",
        )