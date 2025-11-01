"""
Cache invalidation helper - safely clears cache when DB changes
"""
import structlog
from app.cache.redis_client import redis_client

logger = structlog.get_logger(__name__)


class CacheManager:
    """Handles all cache invalidation logic"""

    @staticmethod
    async def _delete_pattern(pattern: str) -> int:
        """
        Delete all Redis keys matching a given pattern.
        Returns number of keys deleted.
        """
        if not redis_client.is_available() or not redis_client.redis:
            logger.warning("redis_unavailable_skip_invalidation", pattern=pattern)
            return 0

        try:
            keys_deleted = 0
            async for key in redis_client.redis.scan_iter(match=pattern, count=100):
                await redis_client.redis.delete(key)
                keys_deleted += 1
            return keys_deleted
        except Exception as e:
            logger.warning("cache_pattern_delete_failed", pattern=pattern, error=str(e))
            return 0

    @staticmethod
    async def invalidate_products():
        """Clear all product list cache keys after create/update/delete"""
        pattern = "products:all*"
        deleted = await CacheManager._delete_pattern(pattern)
        if deleted:
            logger.info("cache_invalidated", entity="products", keys_deleted=deleted)
        return deleted > 0

    # === COMMUNES ===
    @staticmethod
    async def invalidate_communes():
        """Clear all commune list cache keys after create/update/delete"""
        pattern = "communes:all*"
        deleted = await CacheManager._delete_pattern(pattern)
        if deleted:
            logger.info("cache_invalidated", entity="communes", keys_deleted=deleted)
        return deleted > 0

    @staticmethod
    async def invalidate_all():
        """Nuclear option - clear entire Redis DB (use for emergencies only)"""
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
