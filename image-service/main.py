from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from typing import Optional, List
import uuid, os, io

# external singletons you already have:
# minio_client, MINIO_BUCKET, MAX_FILE_SIZE, logger

app = FastAPI()
CHUNK_SIZE = 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------------------------------------------------------
# helpers
# ---------------------------------------------------------

def build_object_name(image_id: str, user_id: Optional[str], ext: str) -> str:
    if user_id:
        return f"{user_id}/{image_id}{ext}"
    return f"{image_id}{ext}"


async def find_object_by_id(image_id: str) -> Optional[str]:
    objects = await run_in_threadpool(
        lambda: list(minio_client.list_objects(MINIO_BUCKET, recursive=True))
    )
    suffixes = (f"{image_id}.jpg", f"{image_id}.png", f"{image_id}.webp")
    for obj in objects:
        if obj.object_name.endswith(suffixes):
            return obj.object_name
    return None


# ---------------------------------------------------------
# upload
# ---------------------------------------------------------

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    user_id: Optional[str] = None
):
    ctype = file.content_type
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    spooled = file.file
    try:
        await run_in_threadpool(spooled.seek, 0, os.SEEK_END)
        size = await run_in_threadpool(spooled.tell)
        await run_in_threadpool(spooled.seek, 0)

        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max {MAX_FILE_SIZE} bytes"
            )

        ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[ctype]

        image_id = str(uuid.uuid4())
        object_name = build_object_name(image_id, user_id, ext)

        await run_in_threadpool(
            minio_client.put_object,
            MINIO_BUCKET,
            object_name,
            spooled,
            length=size,
            content_type=ctype
        )

        logger.info("upload_ok", image_id=image_id, user_id=user_id, size=size)
        return {
            "image_id": image_id,
            "url": f"/images/{image_id}",
            "size": size
        }

    except Exception as e:
        logger.error("upload_fail", error=str(e), exc_info=True)
        raise HTTPException(500, "Upload failed")

    finally:
        try:
            await run_in_threadpool(spooled.close)
        except Exception:
            pass


# ---------------------------------------------------------
# download / stream
# ---------------------------------------------------------

@app.get("/images/{image_id}")
async def get_image(image_id: str):
    object_name = await find_object_by_id(image_id)
    if not object_name:
        raise HTTPException(404, "Image not found")

    try:
        stat = await run_in_threadpool(
            minio_client.stat_object, MINIO_BUCKET, object_name
        )
        length = stat.size
        ctype = stat.content_type or "application/octet-stream"
    except Exception:
        length = None
        ctype = "application/octet-stream"

    try:
        obj = await run_in_threadpool(
            minio_client.get_object, MINIO_BUCKET, object_name
        )
    except Exception as e:
        logger.error("get_fail", error=str(e), image_id=image_id)
        raise HTTPException(500, "Retrieval failed")

    async def stream():
        try:
            while True:
                chunk = await run_in_threadpool(obj.read, CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            try: await run_in_threadpool(obj.close)
            except: pass
            try: await run_in_threadpool(obj.release_conn)
            except: pass

    headers = {
        "Cache-Control": "public, max-age=2592000",
        "Content-Disposition": f'inline; filename="{image_id}"',
    }
    if length is not None:
        headers["Content-Length"] = str(length)

    return StreamingResponse(stream(), media_type=ctype, headers=headers)


# ---------------------------------------------------------
# delete
# ---------------------------------------------------------

@app.delete("/images/{image_id}")
async def delete_image(image_id: str):
    object_name = await find_object_by_id(image_id)
    if not object_name:
        raise HTTPException(404, "Image not found")

    try:
        await run_in_threadpool(
            minio_client.remove_object, MINIO_BUCKET, object_name
        )
        logger.info("delete_ok", image_id=image_id)
        return {"status": "deleted", "image_id": image_id}

    except Exception as e:
        logger.error("delete_fail", error=str(e), image_id=image_id)
        raise HTTPException(500, "Delete failed")


# ---------------------------------------------------------
# list
# ---------------------------------------------------------

@app.get("/images")
async def list_images(user_id: Optional[str] = None):
    prefix = f"{user_id}/" if user_id else None
    objects = await run_in_threadpool(
        lambda: list(minio_client.list_objects(MINIO_BUCKET, prefix=prefix, recursive=True))
    )

    return {
        "count": len(objects),
        "objects": [
            {"name": o.object_name, "size": o.size}
            for o in objects
        ]
    }
