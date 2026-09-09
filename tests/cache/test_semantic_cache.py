"""
This file is supposed to test the Semantic Cache functionality.

Use the following command to run the test:
python -m tests.cache.test_semantic_cache
"""

import asyncio

from app.core.cache.semantic_cache import semantic_cache


async def test_semantic_cache() -> None:

    # Queries and their responses
    test_data = [
        (
            "What is Python?",
            "Python is a high-level programming language.",
        ),
        (
            "What is Redis?",
            "Redis is an in-memory data store.",
        ),
        (
            "What is FastAPI?",
            "FastAPI is a Python web framework.",
        ),
    ]

    # 1. Store multiple responses
    print("\n--- SET ---")

    for query, response in test_data:
        await semantic_cache.set(query, response)
        print(f"Cached: {query}")

    # 2. Test exact queries
    print("\n--- EXACT QUERIES ---")

    for query, expected_response in test_data:
        result = await semantic_cache.get(query)

        print(f"Query: {query}")
        print(f"Result: {result}")

        assert result == expected_response

    # 3. Test semantically similar queries
    print("\n--- SIMILAR QUERIES ---")

    similar_queries = [
        "Can you explain what Python is?",
        "What exactly is Redis?",
        "Can you explain FastAPI?",
    ]

    for query in similar_queries:
        result = await semantic_cache.get(query)

        print(f"Query: {query}")
        print(f"Result: {result}")

    # 4. Test unrelated query
    print("\n--- UNRELATED QUERY ---")

    query = "What is the capital of France?"

    result = await semantic_cache.get(query)

    print(f"Query: {query}")
    print(f"Result: {result}")

    # 5. Statistics
    print("\n--- STATS ---")
    print(semantic_cache.stats)

    # 6. Verify TTL
    print("\n--- TTL ---")

    ttl_query = "What is Docker?"
    ttl_response = "Docker is a containerization platform."

    await semantic_cache.set(ttl_query, ttl_response)

    # Generate the Redis key(s) are random, so we cannot directly
    # calculate the key from the query.
    # For now, verify the configured TTL.
    print(f"Configured TTL: {semantic_cache.ttl} seconds")


if __name__ == "__main__":
    asyncio.run(test_semantic_cache())
