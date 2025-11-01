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
            if not redis_client.is_available():
                return await func(*args, **kwargs)

            safe_kw = {}
            for k, v in kwargs.items():
                if v is None or isinstance(v, (str, int, float, bool, list, dict)):
                    safe_kw[k] = v
                else:
                    safe_kw[k] = f"<nonserializable:{v.__class__.__name__}>"

            try:
                params_str = json.dumps(safe_kw, sort_keys=True, separators=(",", ":"))
            except Exception:
                params_str = str(safe_kw)

            cache_key = f"{key_prefix}:{params_str}"

            if len(cache_key) > 200:
                import hashlib
                cache_key = f"{key_prefix}:{hashlib.sha256(cache_key.encode()).hexdigest()}"

            cached = await redis_client.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass

            result = await func(*args, **kwargs)
            await redis_client.set(cache_key, json.dumps(result), expire=ttl or settings.cache_ttl)
            return result

        return wrapper
    return decorator