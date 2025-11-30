from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
from datetime import datetime
import asyncpg
import structlog
import tempfile

from app.config import settings
from app.database.connection import pool_manager, get_db
from app.redis.redis_client import redis_client
from app.services.file_handler import FileHandler
from app.auth.dependencies import require_admin

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def basic_health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.project_name
    }


@router.get("/detailed/use-postman-or-similar-to-send-csrf")
async def detailed_health(
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db)
) -> dict[str, Any]:
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    overall_healthy = True

    try:
        result = await db.fetchval("SELECT 1")
        pool_size = pool_manager.write_pool.get_size() if pool_manager.write_pool else 0
        health_status["checks"]["database"] = {
            "status": "healthy" if result == 1 else "unhealthy",
            "pool_size": pool_size,
            "max_pool_size": settings.db_pool_max_size
        }
        if result != 1:
            overall_healthy = False
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
        logger.error("health_check_database_failed", exc_info=e)

    try:
        if redis_client.is_available() and redis_client.redis:
            await redis_client.redis.ping()
            redis_status = "healthy"
        else:
            redis_status = "unavailable"
        health_status["checks"]["redis"] = {
            "status": redis_status,
            "available": redis_client.is_available()
        }
        if not redis_client.is_available():
            logger.warning("health_check_redis_unavailable")
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        logger.error("health_check_redis_failed", exc_info=e)

    nsfw_status = FileHandler.get_nsfw_status()
    health_status["checks"]["nsfw_model"] = {
        "status": "healthy" if nsfw_status["available"] else "unavailable",
        "model_loaded": nsfw_status["model_loaded"],
        "threshold": nsfw_status["threshold"]
    }
    if not nsfw_status["available"]:
        logger.warning("health_check_nsfw_unavailable")

    try:
        upload_dir = FileHandler.UPLOAD_DIR
        if upload_dir.exists() and upload_dir.is_dir():
            file_count = len(list(upload_dir.glob("*")))
            with tempfile.NamedTemporaryFile(dir=upload_dir, delete=True) as tmp:
                tmp.write(b"test")
            health_status["checks"]["file_storage"] = {
                "status": "healthy",
                "path": str(upload_dir),
                "file_count": file_count,
                "writable": True
            }
        else:
            health_status["checks"]["file_storage"] = {
                "status": "unhealthy",
                "error": "Upload directory not found or not accessible"
            }
            overall_healthy = False
    except Exception as e:
        health_status["checks"]["file_storage"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
        logger.error("health_check_file_storage_failed", exc_info=e)

    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    if not overall_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    return health_status


@router.get("/database/use-postman-or-similar-to-send-csrf")
async def database_health(
    current_user: dict = Depends(require_admin),
    db: asyncpg.Connection = Depends(get_db)
) -> dict[str, Any]:
    try:
        await db.fetchval("SELECT 1")
        users_count = await db.fetchval("SELECT COUNT(*) FROM proveo.users")
        companies_count = await db.fetchval("SELECT COUNT(*) FROM proveo.companies")
        products_count = await db.fetchval("SELECT COUNT(*) FROM proveo.products")
        communes_count = await db.fetchval("SELECT COUNT(*) FROM proveo.communes")
        pool_size = pool_manager.write_pool.get_size() if pool_manager.write_pool else 0
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "pool": {
                "size": pool_size,
                "max_size": settings.db_pool_max_size
            },
            "tables": {
                "users": users_count,
                "companies": companies_count,
                "products": products_count,
                "communes": communes_count
            }
        }
    except Exception as e:
        logger.error("database_health_check_failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "error": str(e)}
        )
