from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional
from minio import Minio
from minio.error import S3Error
import structlog
from contextlib import asynccontextmanager

from config import settings
from image_validator import ImageValidator

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
    """Application startup and shutdown"""
    try:
        if not await run_in_threadpool(minio_client.bucket_exists, settings.minio_bucket):
            await run_in_threadpool(minio_client.make_bucket, settings.minio_bucket)
            logger.info("bucket_created", bucket=settings.minio_bucket)
        else:
            logger.info("bucket_exists", bucket=settings.minio_bucket)

        if settings.nsfw_enabled:
            nsfw_success = await run_in_threadpool(ImageValidator.init_nsfw_model)
            if not nsfw_success and settings.nsfw_fail_closed:
                logger.warning(
                    "nsfw_model_init_failed_fail_closed_mode",
                    message="Uploads will be blocked if NSFW check cannot run"
                )
        else:
            logger.info("nsfw_detection_disabled")

        logger.info(
            "image_service_started",
            endpoint=settings.minio_endpoint,
            bucket=settings.minio_bucket,
            max_file_size_mb=settings.max_file_size / 1_000_000,
            nsfw_status=ImageValidator.get_nsfw_status()
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

def build_object_name(company_id: str, ext: str) -> str:
    """
    Build MinIO object path using ONLY company_id
    Format: {company_id}.{ext}
    Example: 550e8400-e29b-41d4-a716-446655440001.jpg
    """
    return f"{company_id}{ext}"


async def find_object_by_id(company_id: str) -> Optional[str]:
    """
    Find object in MinIO by company_id using configured extensions.
    Tries each possible {company_id}{ext} and returns the first that exists.
    """
    exts = set(settings.ext_by_format.values())

    for ext in exts:
        object_name = f"{company_id}{ext}"
        try:
            # just check if it exists
            await run_in_threadpool(
                minio_client.stat_object,
                settings.minio_bucket,
                object_name,
            )
            return object_name
        except S3Error as e:
            # Not found or other error — skip to next ext
            # If you want, you can log only non-404 errors
            if getattr(e, "code", None) not in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                logger.warning(
                    "stat_object_error",
                    company_id=company_id,
                    object_name=object_name,
                    error=str(e),
                )
            continue

    return None


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint with NSFW status"""
    try:
        await run_in_threadpool(minio_client.bucket_exists, settings.minio_bucket)
        return {
            "status": "healthy",
            "service": "image-storage",
            "bucket": settings.minio_bucket,
            "nsfw": ImageValidator.get_nsfw_status()
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
    company_id: str = None,
):
    """
    Upload an image to MinIO with validation and NSFW detection
    
    Process:
    1. Validate and process image (resize, optimize)
    2. Check for NSFW content
    3. Upload to MinIO
    
    Returns: company_id (as image_id), url, size, nsfw_score
    """
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required"
        )
    
    spooled = file.file

    try:
        # Step 1: Read raw bytes
        await run_in_threadpool(spooled.seek, 0)
        file_bytes = await run_in_threadpool(spooled.read)
        
        logger.info(
            "upload_started",
            company_id=company_id,
            size_kb=len(file_bytes) / 1024,
            content_type=file.content_type
        )

        # Step 2: Validate and process image
        try:
            processed_bytes, ext = await run_in_threadpool(
                ImageValidator.validate_and_process_image,
                file_bytes,
                file.content_type or "image/jpeg"
            )
        except ValueError as e:
            logger.warning("image_validation_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # Step 3: NSFW check on processed bytes
        nsfw_score, check_performed = await run_in_threadpool(
            ImageValidator.check_nsfw_content,
            processed_bytes
        )

        if nsfw_score > settings.nsfw_threshold:
            if check_performed:
                logger.warning(
                    "nsfw_image_rejected",
                    nsfw_score=nsfw_score,
                    company_id=company_id
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image rejected: inappropriate content detected (confidence: {nsfw_score:.1%})"
                )
            else:
                # NSFW check failed to run - fail closed
                logger.error("nsfw_check_failed_blocking_upload", company_id=company_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Content moderation service unavailable. Please try again later."
                )

        # Step 4: Delete old image if exists (different extension)
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

        # Step 5: Upload to MinIO
        object_name = build_object_name(company_id, ext)
        
        # Determine content type from extension
        content_type_map = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }
        upload_content_type = content_type_map.get(ext, "image/jpeg")
        
        from io import BytesIO
        upload_stream = BytesIO(processed_bytes)
        
        await run_in_threadpool(
            minio_client.put_object,
            settings.minio_bucket,
            object_name,
            upload_stream,
            length=len(processed_bytes),
            content_type=upload_content_type,
        )

        logger.info(
            "upload_success",
            company_id=company_id,
            size=len(processed_bytes),
            object_name=object_name,
            nsfw_score=nsfw_score,
            nsfw_check_performed=check_performed
        )

        return {
            "image_id": company_id,
            "url": f"/images/{company_id}",
            "size": len(processed_bytes),
            "nsfw_score": nsfw_score if check_performed else None,
            "nsfw_checked": check_performed
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