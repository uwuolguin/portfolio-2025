from fastapi import APIRouter, Depends, status
from typing import Any
from datetime import datetime
import asyncpg
import structlog

from app.config import settings
from app.database.connection import pool_manager, get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def basic_health() -> dict[str, Any]:
    """
    Basic health check endpoint for load balancers and monitoring.
    Returns 200 if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.project_name
    }


@router.get("/database")
async def database_health(
    db: asyncpg.Connection = Depends(get_db)
) -> dict[str, Any]:
    """
    Database health check - verifies connection pool and basic query.
    Used for testing and monitoring database connectivity.
    """
    try:
        await db.fetchval("SELECT 1")
        pool_size = pool_manager.write_pool.get_size() if pool_manager.write_pool else 0
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "pool": {
                "size": pool_size,
                "max_size": settings.db_pool_max_size
            }
        }
    except Exception as e:
        logger.error("database_health_check_failed", exc_info=e)
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }