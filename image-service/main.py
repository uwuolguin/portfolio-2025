from fastapi import FastAPI, UploadFile, File, HTTPException, status, Form
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
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
    company_id: str = Form(...),
    extension: str = Form(...),
):
    """
    Upload an image with validation and NSFW detection.
    
    Optimized to minimize memory usage by:
    1. Streaming file from request
    2. Processing in chunks where possible
    3. Only loading full bytes when necessary (validation, NSFW)
    """
    
    spooled = file.file

    try:
        await run_in_threadpool(spooled.seek, 0)
        
        await run_in_threadpool(spooled.seek, 0, 2)
        file_size = await run_in_threadpool(spooled.tell)
        await run_in_threadpool(spooled.seek, 0)
        
        if file_size > settings.max_file_size:
            size_mb = file_size / 1_048_576
            limit_mb = settings.max_file_size / 1_048_576
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image too large ({size_mb:.2f}MB). Limit: {limit_mb:.2f}MB"
            )
        
        file_bytes = await run_in_threadpool(spooled.read)
        
        logger.info(
            "upload_started",
            company_id=company_id,
            extension=extension,
            size_kb=len(file_bytes) / 1024,
            content_type=file.content_type
        )

        try:
            processed_bytes = await run_in_threadpool(
                ImageValidator.validate_and_process_image,
                file_bytes,
                file.content_type,
                extension
            )
        except ValueError as e:
            logger.warning("image_validation_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

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
                logger.error("nsfw_check_failed_blocking_upload", company_id=company_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Content moderation service unavailable. Please try again later."
                )

        object_name = f"{company_id}{extension}"
        
        upload_content_type = settings.content_type_map.get(extension, "application/octet-stream")
        
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
            extension=extension,
            size=len(processed_bytes),
            object_name=object_name,
            nsfw_score=nsfw_score,
            nsfw_check_performed=check_performed
        )

        return {
            "image_id": company_id,
            "extension": extension,
            "url": f"/images/{company_id}{extension}",
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

@app.get("/images/{filename}")
async def get_image(filename: str):
    """
    Stream an image from MinIO using full filename (company_id + extension)
    
    Backend provides complete filename: {company_id}.jpg or {company_id}.png
    """
    object_name = filename
    
    try:
        try:
            stat = await run_in_threadpool(
                minio_client.stat_object, settings.minio_bucket, object_name
            )
            length = stat.size
            ctype = stat.content_type or "application/octet-stream"
        except S3Error as e:
            if getattr(e, "code", None) in ("NoSuchKey", "NoSuchObject"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image not found"
                )
            raise

        obj = await run_in_threadpool(
            minio_client.get_object, settings.minio_bucket, object_name
        )

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
            "Cache-Control": "public, max-age=2592000",
            "Content-Disposition": f'inline; filename="{filename}"',
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
            filename=filename,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retrieval failed",
        )


@app.delete("/images/{filename}")
async def delete_image(filename: str):
    """
    Delete an image from MinIO using full filename (company_id + extension)
    """
    object_name = filename
    
    try:
        try:
            await run_in_threadpool(
                minio_client.stat_object,
                settings.minio_bucket,
                object_name,
            )
        except S3Error as e:
            if getattr(e, "code", None) in ("NoSuchKey", "NoSuchObject"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image not found",
                )
            raise
        
        await run_in_threadpool(
            minio_client.remove_object, settings.minio_bucket, object_name
        )

        logger.info("delete_success", filename=filename)

        return {
            "status": "deleted",
            "filename": filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_failed",
            filename=filename,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )


@app.get("/images")
async def list_images():
    """List all images in the bucket (admin/debugging)"""
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