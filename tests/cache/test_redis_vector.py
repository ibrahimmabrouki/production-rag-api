"""
This test file is responsible for testing the Redis vector storage functionality. It includes a test case that stores a 768-dimensional embedding vector in Redis and verifies its existence. The test uses asyncio to handle asynchronous operations with Redis.
use the following command to run the test:
python -m tests.cache.test_redis_vector

768-dimensional embedding
        ↓
FLOAT32 bytes
        ↓
RedisOperations.store_vector()
        ↓
redis_binary
        ↓
Redis
        ↓
key successfully stored
"""


import asyncio
import numpy as np

from app.core.cache.redis_operations import redis_operations


async def test_store_vector():
    # Create a fake 768-dimensional embedding
    vector = np.random.rand(768).astype(np.float32)

    # Convert it to FLOAT32 bytes
    vector_bytes = vector.tobytes()

    key = "semantic_cache:test"

    result = await redis_operations.store_vector(
        key=key,
        query="What is Python?",
        response="Python is a programming language.",
        embedding=vector_bytes,
        ttl=300,
    )

    print(f"Store result: {result}")

    # Verify the key exists
    exists = await redis_operations.exists(key)

    print(f"Key exists: {exists}")

    # Clean up
    await redis_operations.delete(key)


if __name__ == "__main__":
    asyncio.run(test_store_vector())
