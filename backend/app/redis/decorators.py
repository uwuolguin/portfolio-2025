import json, functools
from typing import Callable, Any
from app.redis.redis_client import redis_client
from app.config import settings
import structlog
from pydantic import BaseModel

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
                    logger.warning("cache_json_decode_error", key=cache_key)
                    pass

            result = await func(*args, **kwargs)
            
            if isinstance(result, list):
                json_result = [
                    item.model_dump(mode='json') if isinstance(item, BaseModel) else item 
                    for item in result
                ]
            elif isinstance(result, BaseModel):
                json_result = result.model_dump(mode='json')
            else:
                json_result = result
            
            await redis_client.set(
                cache_key, 
                json.dumps(json_result), 
                expire=ttl or settings.cache_ttl
            )
            
            return result

        return wrapper
    return decorator