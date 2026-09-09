"""
Redis operations for the application.

"""

from typing import Optional
from app.core.redis.redis_client import redis_client


class RedisOperations:
    """Wrapper methods for Redis operations."""

    # this method is responsible to get the value from the Redis server by key
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis by key."""
        return await redis_client.redis.get(key)

    # this method is responsible to set the value in the Redis server by key and optional TTL
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in Redis with an optional TTL."""
        if ttl is not None:
            return await redis_client.redis.set(
                key,
                value,
                ex=ttl,
            )

        return await redis_client.redis.set(key, value)

    # this method is responsible to delete the value from the Redis server by key
    # it returns the number of keys that were removed
    async def delete(self, key: str) -> int:
        """Delete a key from Redis."""
        return await redis_client.redis.delete(key)

    # this method is responsible to check whether a key exists in the Redis server
    async def exists(self, key: str) -> bool:
        """Check whether a key exists."""
        return bool(await redis_client.redis.exists(key))

    # This method is responsible to get the remaining TTL of a key in the Redis server
    async def ttl(self, key: str) -> int:
        """Return the remaining TTL of a Redis key in seconds."""
        return await redis_client.redis.ttl(key)

    # this method is responsible for storing the key which is assocaited with the query, response and embedding in the Redis server
    async def store_vector(
        self,
        key: str,
        query: str,
        response: str,
        embedding: bytes,
        ttl: int | None = None,
    ) -> bool:
        """Store a semantic-cache entry with its embedding."""

        result = await redis_client.redis_binary.hset(
            key,
            mapping={
                "query": query,
                "response": response,
                "embedding": embedding,
            },
        )

        if ttl is not None:
            await redis_client.redis_binary.expire(key, ttl)

        return bool(result)

    # This is vector search method that will be used to search for similar vectors in the Redis server

    async def vector_search(
        self,
        index_name: str,
        query_vector: bytes,
        top_k: int = 1,
    ):
        """Search for the nearest vectors in Redis."""

        query = f"*=>[KNN {top_k} @embedding $vector AS distance]"

        return await redis_client.redis_binary.ft(index_name).search(
            query,
            query_params={"vector": query_vector},
        )


redis_operations = RedisOperations()
