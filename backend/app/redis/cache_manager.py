import structlog
from app.redis.redis_client import redis_client

logger = structlog.get_logger(__name__)


class CacheManager:
    @staticmethod
    async def _delete_key(key: str) -> bool:
        if not redis_client.is_available() or not redis_client.redis:
            logger.warning("redis_unavailable_skip_invalidation", key=key)
            return False

        try:
            deleted = await redis_client.delete(key)
            return deleted
        except Exception as e:
            logger.warning("cache_key_delete_failed", key=key, error=str(e))
            return False

    @staticmethod
    async def invalidate_products():
        key = "products:all"
        deleted = await CacheManager._delete_key(key)
        if deleted:
            logger.info("cache_invalidated", entity="products", key_deleted=key)
        return deleted

    @staticmethod
    async def invalidate_communes():
        key = "communes:all"
        deleted = await CacheManager._delete_key(key)
        if deleted:
            logger.info("cache_invalidated", entity="communes", key_deleted=key)
        return deleted

    @staticmethod
    async def invalidate_all():
        if not redis_client.is_available() or not redis_client.redis:
            logger.warning("redis_unavailable_skip_flush")
            return False

        try:
            await redis_client.redis.flushdb()
            logger.warning("cache_nuked", message="All cache cleared")
            return True
        except Exception as e:
            logger.error("cache_nuke_failed", error=str(e))
            return False


cache_manager = CacheManager()
