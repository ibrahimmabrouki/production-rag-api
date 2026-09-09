"""
Test the Cache Manager.

Run:
python -m tests.cache.test_cache_manager
"""

import asyncio

from app.core.cache.cache_manager import CacheManager


async def test_cache_manager() -> None:
    cache_manager = CacheManager()

    # --------------------------------------------------
    # 1. Store test data
    # --------------------------------------------------

    query = "What is Python?"
    response = "Python is a programming language."

    print("\n--- SET ---")

    await cache_manager.set(query, response)

    print(f"Cached: {query}")

    # --------------------------------------------------
    # 2. Exact cache hit
    # --------------------------------------------------

    print("\n--- EXACT CACHE HIT ---")

    is_cache, returned_query, returned_response, cache_type = (
        await cache_manager.get(query)
    )

    print(f"is_cache: {is_cache}")
    print(f"query: {returned_query}")
    print(f"response: {returned_response}")
    print(f"cache_type: {cache_type}")

    assert is_cache is True
    assert returned_query == query
    assert returned_response == response

    # --------------------------------------------------
    # 3. Semantic cache hit
    # --------------------------------------------------

    print("\n--- SEMANTIC CACHE HIT ---")

    similar_query = "Can you explain what Python is?"

    is_cache, returned_query, returned_response, cache_type = (
        await cache_manager.get(similar_query)
    )

    print(f"is_cache: {is_cache}")
    print(f"query: {returned_query}")
    print(f"response: {returned_response}")
    print(f"cache_type: {cache_type}")

    assert is_cache is True
    assert returned_query == similar_query
    assert returned_response == response

    # --------------------------------------------------
    # 4. Cache miss
    # --------------------------------------------------

    print("\n--- CACHE MISS ---")

    new_query = "What is the capital of France?"

    is_cache, returned_query, returned_response, cache_type = (
        await cache_manager.get(new_query)
    )

    print(f"is_cache: {is_cache}")
    print(f"query: {returned_query}")
    print(f"response: {returned_response}")
    print(f"cache_type: {cache_type}")

    assert is_cache is False
    assert returned_query == new_query
    assert returned_response is None

    # --------------------------------------------------
    # 5. Statistics
    # --------------------------------------------------

    print("\n--- STATS ---")

    print(cache_manager.stats)


if __name__ == "__main__":
    asyncio.run(test_cache_manager())
