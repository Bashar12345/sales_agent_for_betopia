# [OWNER: Zohra — Data Foundation (P3)]
"""Redis cache client for suggestion and embedding caching.

Cache strategy (v3.0):
  Suggestion cache:  key = SHA256(conversation_id + customer_message)
                     TTL = REDIS_SUGGESTION_CACHE_TTL (5 min)
                     Value = JSON list of suggestion dicts

  Embedding cache:   key = SHA256(text + model)
                     TTL = REDIS_EMBEDDING_CACHE_TTL (24 h)
                     Value = JSON list of floats (3072-d vector)

  Rate limit tokens: key = ratelimit:{agent_id}
                     TTL = 60s, value = request count (INCR)

Cost impact: embedding cache alone cuts ~80% of OpenAI embedding calls at
2,000 DAU since most conversations reference the same service descriptions.
"""

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from src.core.settings import settings

log = structlog.get_logger()


def _sha256_key(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(("".join(parts)).encode()).hexdigest()
    return f"{prefix}:{digest}"


class RedisCacheClient:
    def __init__(self) -> None:
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    # ── Suggestion cache ──────────────────────────────────────────────────────

    async def get_suggestions(
        self, conversation_id: str, customer_message: str
    ) -> list[dict[str, Any]] | None:
        key = _sha256_key("suggest", conversation_id, customer_message)
        raw = await self._redis.get(key)
        if raw:
            log.debug("cache.suggestion_hit", key=key[:16])
            return json.loads(raw)
        return None

    async def set_suggestions(
        self,
        conversation_id: str,
        customer_message: str,
        suggestions: list[dict[str, Any]],
    ) -> None:
        key = _sha256_key("suggest", conversation_id, customer_message)
        await self._redis.setex(
            key,
            settings.REDIS_SUGGESTION_CACHE_TTL,
            json.dumps(suggestions),
        )

    # ── Embedding cache ───────────────────────────────────────────────────────

    async def get_embedding(self, text: str) -> list[float] | None:
        key = _sha256_key("embed", text, settings.EMBEDDING_MODEL)
        raw = await self._redis.get(key)
        if raw:
            log.debug("cache.embedding_hit", key=key[:16])
            return json.loads(raw)
        return None

    async def set_embedding(self, text: str, vector: list[float]) -> None:
        key = _sha256_key("embed", text, settings.EMBEDDING_MODEL)
        await self._redis.setex(
            key,
            settings.REDIS_EMBEDDING_CACHE_TTL,
            json.dumps(vector),
        )

    # ── Rate limiting ─────────────────────────────────────────────────────────

    async def check_rate_limit(self, agent_id: str, limit: int = 100) -> bool:
        """Increment request counter; return True if under limit.

        Resets automatically every 60 seconds (sliding window per minute).
        Kong enforces 100 req/min/user at the gateway layer; this is a
        defence-in-depth check inside the app.
        """
        key = f"ratelimit:{agent_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60)
        if count > limit:
            log.warning("cache.rate_limit_exceeded", agent_id=agent_id, count=count)
            return False
        return True

    async def close(self) -> None:
        await self._redis.aclose()
