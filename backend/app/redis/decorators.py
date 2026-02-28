import json, functools
from typing import Callable, Any
from app.redis.redis_client import redis_client
from app.config import settings
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# =============================================================================
# HOW DECORATORS WORK — explained through this exact implementation
# =============================================================================
#
# A decorator is just a function OR ANY CALLABLE that receives a function and returns a new
# function in its place. The @ syntax is pure sugar:
#
#   @cache_response(key_prefix="communes:all", ttl=259200)
#   async def list_communes(db = Depends(get_db_read)):
#       ...
#
# Python reads that exactly as:
#   list_communes = cache_response(key_prefix="communes:all", ttl=259200)(list_communes)
#
# -----------------------------------------------------------------------------
# WHY THREE LEVELS OF NESTING?
# -----------------------------------------------------------------------------
# A plain decorator can only receive the function — nothing else:
#   @my_decorator          → my_decorator(list_communes)
#   @my_decorator(ttl=60)  → impossible with a plain decorator
#
# To pass config (key_prefix, ttl), we need a factory — a function that
# receives the config and RETURNS a decorator. That adds one level:
#
#   cache_response(key_prefix, ttl)  → FACTORY, called once at module load,
#                                       closes over key_prefix and ttl,
#                                       returns decorator
#
#   decorator(func)                  → DECORATOR, receives list_communes,
#                                       closes over func,
#                                       returns wrapper
#
#   wrapper(*args, **kwargs)         → REPLACEMENT, this is what actually
#                                       runs on every HTTP request
#
# -----------------------------------------------------------------------------
# WHAT IS A CLOSURE?
# -----------------------------------------------------------------------------
# When decorator(func) runs, it creates wrapper and returns it. At that point
# decorator is done — but wrapper still holds references to key_prefix, ttl,
# and func even though the outer functions finished. Those variables are
# "closed over" — they live in wrapper's scope forever. That's a closure.
#
# -----------------------------------------------------------------------------
# FUNCTOOLS.WRAPS — what it does and how
# -----------------------------------------------------------------------------
# After decorator(list_communes) runs, the name list_communes now points to
# wrapper in memory. The original function is gone from that name. Problem:
# wrapper.__name__ is literally "wrapper", not "list_communes". FastAPI uses
# the function name and signature for dependency injection and OpenAPI docs —
# if it sees "wrapper" with *args, **kwargs it breaks.
#
# functools.wraps(func) fixes this by copying metadata from the original
# function onto wrapper. Under the hood:
#
#   functools.wraps(func)
#   → returns partial(update_wrapper, wrapped=func, assigned=..., updated=...)
#   → that partial is callable, so @ applies it: partial.__call__(wrapper)
#   → which calls: update_wrapper(wrapper, wrapped=func, ...)
#   → which does:
#       wrapper.__name__     = func.__name__      # "list_communes"
#       wrapper.__qualname__ = func.__qualname__
#       wrapper.__doc__      = func.__doc__
#       wrapper.__module__   = func.__module__
#       wrapper.__wrapped__  = func               # keeps ref to original
#
# __wrapped__ is the key one — FastAPI follows it to find the real signature
# and resolve Depends() correctly, then passes db through kwargs to wrapper,
# which forwards it to func(*args, **kwargs) — the real list_communes.
#
# Note: functools.wraps is itself a decorator factory (same pattern as ours)
# except it uses partial instead of a nested function. partial is just a
# callable class — it stores func, args, keywords and calls them later via
# __call__. Same concept, different implementation.
#
# -----------------------------------------------------------------------------
# AT REQUEST TIME — what actually happens
# -----------------------------------------------------------------------------
# 1. HTTP request arrives → FastAPI calls wrapper(db=<connection>)
# 2. wrapper checks Redis first
#    - hit + data     → return immediately, list_communes never called
#    - hit + empty    → stale, delete key, fall through
#    - hit + bad JSON → corrupted, delete key, fall through
#    - miss           → fall through
# 3. cache miss → wrapper calls func(db=<connection>) → hits the DB
# 4. result serialized to JSON (Pydantic models need .model_dump first,
#    mode='json' ensures UUID/datetime become strings not Python objects)
# 5. stored in Redis with TTL
# 6. original Pydantic objects returned to FastAPI for response validation
#    (not json_result — FastAPI needs the models, not the dicts)
# =============================================================================
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
                    data = json.loads(cached)
                    if data:  # non-empty, return it
                        return data
                    else:
                        # empty list/dict cached — stale, flush and fall through to DB
                        await redis_client.delete(cache_key)
                        logger.warning("cache_empty_value_flushed", key=cache_key)
                except json.JSONDecodeError:
                    logger.warning("cache_json_decode_error", key=cache_key)
                    await redis_client.delete(cache_key)  # also clean up bad data

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