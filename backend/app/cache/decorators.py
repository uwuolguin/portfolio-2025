import json, functools
from typing import Callable, Any
from app.cache.redis_client import redis_client
from app.config import settings
import structlog

logger = structlog.get_logger(__name__)

def cache_response(key_prefix: str, ttl: int = None):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            cache_key = key_prefix
            
            if not redis_client.is_available():
                return await func(*args, **kwargs)

            cached = await redis_client.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass

            result = await func(*args, **kwargs)
            
            await redis_client.set(
                cache_key, 
                json.dumps(result), 
                expire=ttl or settings.cache_ttl
            )
            return result

        return wrapper
    return decorator