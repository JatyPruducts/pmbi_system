import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_get_json(key: str) -> Any | None:
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set_json(key: str, value: Any, ttl_seconds: int = 3600) -> None:
    r = await get_redis()
    await r.setex(key, ttl_seconds, json.dumps(value, default=str))
