"""
Redis is an in-memory key-value data store. For RAG API, it is useful because cache operations are extremely fast.

User Query
    ↓
FastAPI
    ↓
Cache Manager
    ├── Exact Cache → Redis
    │
    └── Semantic Cache → Redis + vector/search mechanism
    ↓
If cache miss
    ↓
RAG Pipeline
    ↓
LLM

1-Exact query caching: "What did I spend on food?" → cached response
2-Semantic caching: "How much did I spend on restaurants?" and "What did I spend eating out?"

TTL/expiration
Fast reads/writes
Centralized cache shared by multiple FastAPI workers
Production deployments where multiple API instances need the same cache

The exact_cache.py and semantic_cache.py should eventually depend on a Redis client abstraction, not create Redis connections themselves.

"""

"""
These Below are documentation for what is implemented in the Redis

We have build the redis server in redis container using official redis image. The redis server is running in Docker cantainer 

Now we will implement the Redis client in the app/core/cache/redis_client.py file. This client will be used by the exact_cache.py and semantic_cache.py to interact with the Redis server.

Settings
   ↓
Redis URL
   ↓
Connection Pool
   ↓
Async Redis Client
   ↓
FastAPI / Cache layers

The cache classes should not create their own Redis connections.

- one connection pool
- centralized configuration
- proper timeouts
- connection reuse
- easier testing
- easier production configuration

"""

# this will allow us to use the Redis client in an async way, which is important for FastAPI
from redis.asyncio import Redis
from app.core.config import get_settings


class RedisClient:
    """Centralized async Redis client for the application."""

    def __init__(self) -> None:
        # get the settings from the config.py file
        self.settings = get_settings()

        self.redis = Redis.from_url(
            self.settings.redis_url,
            max_connections=self.settings.redis_max_connections,
            socket_timeout=self.settings.redis_socket_timeout,
            socket_connect_timeout=self.settings.redis_socket_connect_timeout,
            health_check_interval=self.settings.redis_health_check_interval,
            decode_responses=True,
        )
        
        
        # Binary operations (embeddings)
        # this is going to be used for the semantic cache, where we will store the embeddings as binary data in Redis
        self.redis_binary = Redis.from_url(
            self.settings.redis_url,
            max_connections=self.settings.redis_max_connections,
            socket_timeout=self.settings.redis_socket_timeout,
            socket_connect_timeout=self.settings.redis_socket_connect_timeout,
            health_check_interval=self.settings.redis_health_check_interval,
            decode_responses=False,
        )

    async def ping(self) -> bool:
        """Check whether Redis is reachable."""
        try:
            return await self.redis.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Close the Redis connection pool."""
        await self.redis.aclose()


redis_client = RedisClient()

# Pydantic Settings
#        ↓
# Redis configuration
#        ↓
# Redis Python client
#        ↓
# Connection pool
#        ↓
# Docker Redis
#        ↓
# PING
#        ↓
# True


# the next step is building the wrapper methods that will be used in each cache class (exact_cache.py and semantic_cache.py) to interact with the Redis server. These methods will be implemented in the Redis operations class.

# note: redis_client.py

# Responsible only for:

# Creating the Redis client
# Connection pool
# Configuration
# Timeouts
# Health check
# Closing the client

# continue the implementation in redis_operations.py