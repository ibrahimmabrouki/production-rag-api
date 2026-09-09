"""
This File is supposed to test the Redis Client functionality
use the following command to run the test:
python -m tests.cache.test_redis_client
"""

import asyncio

from app.core.redis.redis_client import redis_client


async def main():
    result = await redis_client.ping()

    print(f"Redis connection successful: {result}")

    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
