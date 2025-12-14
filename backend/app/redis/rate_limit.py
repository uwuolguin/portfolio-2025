import time
from fastapi import Request, HTTPException, status
from app.redis.redis_client import redis_client
import structlog

logger = structlog.get_logger(__name__)


async def enforce_rate_limit(
    request: Request,
    route_name: str,
    ip_limit: int,
    global_limit: int,
    window_seconds: int = 60,
):
    """
    Enforces per-IP and global rate limits using Redis counters.
    """

    if not redis_client.is_available():
        logger.warning("redis_unavailable_skip_rate_limit")
        return

    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"

    now = int(time.time())
    window = now // window_seconds

    ip_key = f"rl:{route_name}:ip:{client_ip}:{window}"
    global_key = f"rl:{route_name}:global:{window}"

    async with redis_client.redis.pipeline(transaction=True) as pipe:
        pipe.incr(ip_key)
        pipe.expire(ip_key, window_seconds)
        pipe.incr(global_key)
        pipe.expire(global_key, window_seconds)
        ip_count, _, global_count, _ = await pipe.execute()

    if ip_count > ip_limit:
        logger.warning("rate_limit_ip_exceeded", ip=client_ip, route=route_name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests from this IP (max {ip_limit}/min)."
        )

    if global_count > global_limit:
        logger.warning("rate_limit_global_exceeded", route=route_name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests globally (max {global_limit}/min)."
        )