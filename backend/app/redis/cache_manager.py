"""Cache invalidation helpers built on top of the Redis client."""

import structlog

from app.redis.redis_client import redis_client

logger = structlog.get_logger(__name__)


class CacheManager:
    """Utility class for invalidating cached data in Redis."""

    @staticmethod
    async def _delete_key(key: str) -> bool:
        """Delete a single cache key; returns False if Redis is unavailable."""
        if not redis_client.is_available() or not redis_client.redis:
            logger.warning("redis_unavailable_skip_invalidation", key=key)
            return False

        try:
            deleted = await redis_client.delete(key)
            return deleted
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("cache_key_delete_failed", key=key, error=str(e))
            return False

    @staticmethod
    async def invalidate_products() -> bool:
        """Remove the products list cache entry."""
        key = "products:all"
        deleted = await CacheManager._delete_key(key)
        if deleted:
            logger.info("cache_invalidated", entity="products", key_deleted=key)
        return deleted

    @staticmethod
    async def invalidate_communes() -> bool:
        """Remove the communes list cache entry."""
        key = "communes:all"
        deleted = await CacheManager._delete_key(key)
        if deleted:
            logger.info("cache_invalidated", entity="communes", key_deleted=key)
        return deleted

    @staticmethod
    async def invalidate_all() -> bool:
        """Flush the entire Redis database — use with care."""
        if not redis_client.is_available() or not redis_client.redis:
            logger.warning("redis_unavailable_skip_flush")
            return False

        try:
            await redis_client.redis.flushdb()
            logger.warning("cache_nuked", message="All cache cleared")
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("cache_nuke_failed", error=str(e))
            return False


cache_manager = CacheManager()
