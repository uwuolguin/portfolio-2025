"""
Optimized Image Storage Microservice
- Handles all image CRUD operations
- Uses MinIO for S3-compatible object storage
- Streaming responses for efficient large file handling
- Proper resource cleanup and error handling
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional
from minio import Minio
from minio.error import S3Error
import structlog
import uuid
import os
from contextlib import asynccontextmanager

# ============================================================================
# CONFIGURATION
# ============================================================================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "images")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10_000_000))  # 10MB
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# ============================================================================
# LOGGING SETUP
# ============================================================================
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

# ============================================================================
# MINIO CLIENT INITIALIZATION
# ============================================================================
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MinIO bucket on startup"""
    try:
        # Create bucket if it doesn't exist
        if not await run_in_threadpool(minio_client.bucket_exists, MINIO_BUCKET):
            await run_in_threadpool(minio_client.make_bucket, MINIO_BUCKET)
            logger.info("bucket_created", bucket=MINIO_BUCKET)
        else:
            logger.info("bucket_exists", bucket=MINIO_BUCKET)
        
        logger.info("image_service_started", 
                   endpoint=MINIO_ENDPOINT, 
                   bucket=MINIO_BUCKET,
                   max_file_size_mb=MAX_FILE_SIZE / 1_000_000)
    except Exception as e:
        logger.error("startup_failed", error=str(e), exc_info=True)
        raise
    
    yield
    
    logger.info("image_service_shutdown")

app = FastAPI(
    title="Image Storage Service",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def build_object_name(image_id: str, user_id: Optional[str], ext: str) -> str:
    """Build MinIO object path"""
    if user_id:
        return f"{user_id}/{image_id}{ext}"
    return f"{image_id}{ext}"

async def find_object_by_id(image_id: str) -> Optional[str]:
    """Find object in MinIO by image_id (searches all extensions)"""
    try:
        objects = await run_in_threadpool(
            lambda: list(minio_client.list_objects(MINIO_BUCKET, recursive=True))
        )
        
        suffixes = (f"{image_id}.jpg", f"{image_id}.png", f"{image_id}.webp")
        
        for obj in objects:
            if obj.object_name.endswith(suffixes):
                return obj.object_name
        
        return None
    except S3Error as e:
        logger.error("find_object_failed", image_id=image_id, error=str(e))
        return None

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test MinIO connection
        await run_in_threadpool(minio_client.bucket_exists, MINIO_BUCKET)
        return {
            "status": "healthy",
            "service": "image-storage",
            "bucket": MINIO_BUCKET
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MinIO connection failed"
        )

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    user_id: Optional[str] = None
):
    """
    Upload an image to MinIO
    Returns: image_id, url, size
    """
    # Validate content type
    ctype = file.content_type
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ctype}"
        )
    
    spooled = file.file
    
    try:
        # Check file size
        await run_in_threadpool(spooled.seek, 0, os.SEEK_END)
        size = await run_in_threadpool(spooled.tell)
        await run_in_threadpool(spooled.seek, 0)
        
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max {MAX_FILE_SIZE / 1_000_000}MB"
            )
        
        # Determine extension
        ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[ctype]
        
        # Generate unique ID and object name
        image_id = str(uuid.uuid4())
        object_name = build_object_name(image_id, user_id, ext)
        
        # Upload to MinIO
        await run_in_threadpool(
            minio_client.put_object,
            MINIO_BUCKET,
            object_name,
            spooled,
            length=size,
            content_type=ctype
        )
        
        logger.info("upload_success", 
                   image_id=image_id, 
                   user_id=user_id, 
                   size=size,
                   object_name=object_name)
        
        return {
            "image_id": image_id,
            "url": f"/images/{image_id}",
            "size": size
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed"
        )
    finally:
        try:
            await run_in_threadpool(spooled.close)
        except Exception:
            pass

@app.get("/images/{image_id}")
async def get_image(image_id: str):
    """
    Stream an image from MinIO
    Efficient for large files - uses chunked streaming
    """
    # Find the object
    object_name = await find_object_by_id(image_id)
    
    if not object_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    try:
        # Get object metadata
        try:
            stat = await run_in_threadpool(
                minio_client.stat_object, MINIO_BUCKET, object_name
            )
            length = stat.size
            ctype = stat.content_type or "application/octet-stream"
        except Exception:
            length = None
            ctype = "application/octet-stream"
        
        # Get object stream
        obj = await run_in_threadpool(
            minio_client.get_object, MINIO_BUCKET, object_name
        )
        
        # Stream generator
        async def stream_generator():
            try:
                while True:
                    chunk = await run_in_threadpool(obj.read, CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                # Cleanup
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
            "Content-Disposition": f'inline; filename="{image_id}"',
        }
        
        if length is not None:
            headers["Content-Length"] = str(length)
        
        return StreamingResponse(
            stream_generator(),
            media_type=ctype,
            headers=headers
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_image_failed", 
                    image_id=image_id, 
                    error=str(e), 
                    exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retrieval failed"
        )

@app.delete("/images/{image_id}")
async def delete_image(image_id: str):
    """Delete an image from MinIO"""
    object_name = await find_object_by_id(image_id)
    
    if not object_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    try:
        await run_in_threadpool(
            minio_client.remove_object, MINIO_BUCKET, object_name
        )
        
        logger.info("delete_success", image_id=image_id, object_name=object_name)
        
        return {
            "status": "deleted",
            "image_id": image_id
        }
    
    except Exception as e:
        logger.error("delete_failed", 
                    image_id=image_id, 
                    error=str(e), 
                    exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed"
        )

@app.get("/images")
async def list_images(user_id: Optional[str] = None):
    """List all images (optionally filtered by user_id)"""
    try:
        prefix = f"{user_id}/" if user_id else None
        
        objects = await run_in_threadpool(
            lambda: list(minio_client.list_objects(
                MINIO_BUCKET, 
                prefix=prefix, 
                recursive=True
            ))
        )
        
        return {
            "count": len(objects),
            "objects": [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                }
                for obj in objects
            ]
        }
    
    except Exception as e:
        logger.error("list_images_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list images"
        )