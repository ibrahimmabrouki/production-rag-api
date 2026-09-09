"""
This File is supposed to test the Exact Cache functionality
use the following command to run the test:
python -m tests.cache.test_exact_cache
"""


import asyncio

from app.core.cache.exact_cache import exact_cache


async def test_exact_cache() -> None:
    query = "What is Python?"
    response = "Python is a programming language."

    # 1. First request → cache miss
    result = await exact_cache.get(query)
    print(f"First GET: {result}")

    # 2. Store response
    await exact_cache.set(query, response)
    print("SET: response cached")

    # 3. Second request → cache hit
    result = await exact_cache.get(query)
    print(f"Second GET: {result}")

    # 4. Check statistics
    print(f"Stats: {exact_cache.stats}")

    # 5. Delete
    await exact_cache.delete(query)

    # 6. Verify deletion
    result = await exact_cache.get(query)
    print(f"GET after DELETE: {result}")

    print(f"Final Stats: {exact_cache.stats}")


if __name__ == "__main__":
    asyncio.run(test_exact_cache())
