"""
Exact/identical query cache using Redis.

Identical queries should not repeatedly consume LLM resources.
Redis provides:
- Persistence across application restarts
- Shared cache across multiple API instances
- Native TTL expiration
"""

# ExactCache
#     ↓
# RedisOperations
#     ↓
# Redis

import hashlib
import json
from typing import Optional

from app.core.cache.redis_operations import redis_operations
from app.core.config import get_settings


class ExactCache:
    """Redis-backed cache for identical queries."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.ttl = self.settings.cache_ttl_seconds

        self._hits = 0
        self._misses = 0

    # this method is responsible to create a deterministic Redis key from a normalized query
    def _make_key(self, query: str) -> str:
        """
        Create a deterministic Redis key from a normalized query.
        """
        normalized = query.lower().strip()
        query_hash = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

        # This namespace is useful because later you'll have semantic caching too:
        # cache:exact:...
        # cache:semantic:...
        return f"cache:exact:{query_hash}"

    # this method is responsible to get the value from the Redis server by key
    async def get(self, query: str) -> Optional[str]:
        """
        Get a cached response.

        Returns:
            Cached response if found.
            None if there is a cache miss.
        """
        # Create a deterministic Redis key from the normalized query
        key = self._make_key(query)

        # Get the cached data from Redis
        cached_data = await redis_operations.get(key)

        # If there is no cached data, increment the miss counter and return None
        if cached_data is None:
            self._misses += 1
            return None

        # If there is cached data, increment the hit counter and return the response
        self._hits += 1

        data = json.loads(cached_data)

        return data["response"]

    # this method is responsible to set the value in the Redis server by key and optional TTL
    async def set(self, query: str, response: str) -> None:
        """Cache a response with the configured TTL."""
        
        # Create a deterministic Redis key from the normalized query
        key = self._make_key(query)

        # Store the response in Redis with the configured TTL
        # as JSON so we can later add metadata without changing the Redis structure.
        data = {
            "query": query,
            "response": response,
        }

        # Use the Redis operations wrapper to set the value in Redis with TTL
        await redis_operations.set(
            key,
            json.dumps(data),
            ttl=self.ttl,
        )

    # this method is responsible to delete the value from the Redis server by key
    # it returns the number of keys that were removed
    async def delete(self, query: str) -> None:
        """Delete a cached response."""
        key = self._make_key(query)

        await redis_operations.delete(key)

    # this method is responsible to check whether a key exists in the Redis server
    @property
    def stats(self) -> dict:
        """Return cache performance statistics."""
        total = self._hits + self._misses

        hit_rate = (
            self._hits / total
            if total > 0
            else 0.0
        )

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
        }


exact_cache = ExactCache()
