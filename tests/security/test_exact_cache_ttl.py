"""
This file is supposed to test the TTL (Time To Live) functionality of the ExactCache class.
Use the following command to run the test:
python -m tests.security.test_exact_cache_ttl
"""
# SET
#  ↓
# Redis stores value
#  ↓
# TTL = 2 seconds
#  ↓
# 2+ seconds pass
#  ↓
# Redis automatically removes key
#  ↓
# GET
#  ↓
None

import asyncio

from app.core.cache.exact_cache import ExactCache


async def test_exact_cache_ttl() -> None:
    cache = ExactCache()

    # Use a short TTL specifically for this test.
    cache.ttl = 2

    query = "What is Redis?"
    response = "Redis is an in-memory data store."

    # 1. Store the response
    await cache.set(query, response)
    print("Response cached.")

    # 2. Immediately retrieve it
    result = await cache.get(query)
    print(f"Immediately after SET: {result}")

    # 3. Wait for Redis TTL to expire
    print("Waiting 3 seconds for TTL to expire...")
    await asyncio.sleep(3)

    # 4. Try to retrieve it again
    result = await cache.get(query)
    print(f"After TTL expiration: {result}")


if __name__ == "__main__":
    asyncio.run(test_exact_cache_ttl())