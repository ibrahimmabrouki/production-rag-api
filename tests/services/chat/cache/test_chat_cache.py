"""
Test real cache behavior through ChatService.

Real:
- SecurityPipeline
- ProductionAgent
- CacheManager
- ExactCache
- SemanticCache
- Redis
- Gemini embeddings

Dummy:
- TokenBudget
- ChatUsageRepository

Tests:
1. Cache MISS -> real agent
2. Exact cache HIT
3. Semantic cache HIT
4. Worker-local cache statistics

Run:

python -m tests.services.chat.cache.test_chat_cache
"""

import asyncio

from app.services.chat_service import ChatService
from app.core.security.pipeline import SecurityPipeline
from app.core.cache.cache_manager import CacheManager
from app.agents.agent import ProductionAgent
from app.core.token_budget.chat_usage import ChatUsage
from app.core.redis.redis_client import redis_client


# ============================================================
# DUMMY TOKEN BUDGET
# ============================================================

"""
since our purpose is only to test the real cache
=> create a dummy token budget that will allow every request and will just return a fixed number of tokens for the input and output
=> always allow the request to pass the token budget check
"""


class DummyTokenBudget:

    max_chat_tokens = 1_000_000
    max_requests_per_chat = 1_000_000

    def check_input(self, text: str):
        return True, 10

    def check_chat(
        self,
        usage,
        estimated_input_tokens: int,
    ):
        return True, None

    def estimate_tokens(self, text: str):
        return 10


# ============================================================
# DUMMY CHAT USAGE REPOSITORY
# ============================================================

"""
since our purpose is only to test the real cache
=> create a dummy chat usage repository that will just return a fixed response that allow the test to proceed
"""


class DummyChatUsageRepository:

    async def get_usage(self, chat_id: str):
        return ChatUsage()

    async def reserve_request(
        self,
        chat_id: str,
        estimated_input_tokens: int,
        max_chat_tokens: int,
        max_requests_per_chat: int,
    ):
        return True, None

    async def record_output_usage(
        self,
        chat_id: str,
        output_tokens: int,
    ):
        pass


# ============================================================
# HELPERS
# ============================================================

def print_result(
    name: str,
    passed: bool,
):
    print(
        f"\n{name}: "
        f"{'PASS' if passed else 'FAIL'}"
    )

"""
sicne our purpose is only to test the real cache
then we need to create a helper function that will clear the cache key values in the redis database
this way we can make sure that the cache is empty before we start the test and we can also make sure that the cache is empty after we finish the test
"""

async def clear_cache():
    """
    Clear ONLY cache keys.

    Does not touch:
    - token usage
    - Redis index
    - other Redis application data
    """

    keys = []

    async for key in redis_client.redis.scan_iter(
        match="cache:exact:*"
    ):
        keys.append(key)

    async for key in redis_client.redis.scan_iter(
        match="cache:semantic:*"
    ):
        keys.append(key)

    if keys:
        await redis_client.redis.delete(*keys)

    print(
        f"Cleared {len(keys)} existing cache entries."
    )


"""
This is a helper function that will allow us to reset the cache statistics for this worker process
This is important because the cache statistics are stored in memory and are not shared between workers
"""

def reset_worker_stats(
    cache_manager: CacheManager,
):
    """
    Cache statistics are Python-process/worker local.
    """

    cache_manager.exact_cache._hits = 0
    cache_manager.exact_cache._misses = 0

    cache_manager.semantic_cache._hits = 0
    cache_manager.semantic_cache._misses = 0


# ============================================================
# CREATE SERVICE
# ============================================================

def create_service():

    security_pipeline = SecurityPipeline()
    """
    here in addition that we are assigning actual security pipeline
    the we are also creating and assigning a real cache manager that will use the real exact cache and semantic cache
    """
    
    cache_manager = CacheManager()

    # REAL agent
    agent = ProductionAgent()

    service = ChatService(
        security_pipeline=security_pipeline,
        cache_manager=cache_manager,
        agent=agent,
        token_budget=DummyTokenBudget(),
        chat_usage_repository=(
            DummyChatUsageRepository()
        ),
    )

    return service, cache_manager


# ============================================================
# MAIN
# ============================================================

async def main():

    print("\n" + "=" * 70)
    print("CHAT SERVICE CACHE TEST")
    print("=" * 70)

    service, cache_manager = create_service()

    # Start from deterministic empty cache
    await clear_cache()

    # Reset THIS worker's counters
    reset_worker_stats(cache_manager)

    # ========================================================
    # TEST 1 - CACHE MISS
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 1 - CACHE MISS")
    print("=" * 70)

    original_query = (
        "Explain what Python programming language is "
        "in one short sentence."
    )

    first_response = await service.process(
        message=original_query,
        thread_id="chat-cache-test",
    )

    print("\nResponse:")
    print(first_response)

    print("\nCache type:")
    print(first_response["cache_type"])

    print("\nModel used:")
    print(first_response["model_used"])

    miss_passed = (
        first_response["success"] is True
        and first_response["cached"] is False
        and first_response["cache_type"] is None
        and first_response["model_used"] is not None
        and first_response["response"] is not None
    )

    print_result(
        "CACHE MISS -> REAL AGENT",
        miss_passed,
    )

    # ========================================================
    # TEST 2 - EXACT CACHE HIT
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 2 - EXACT CACHE HIT")
    print("=" * 70)

    exact_response = await service.process(
        message=original_query,
        thread_id="chat-cache-test",
    )

    print("\nResponse:")
    print(exact_response)

    print("\nCached:")
    print(exact_response["cached"])

    print("\nCache type:")
    print(exact_response["cache_type"])

    print("\nModel used:")
    print(exact_response["model_used"])

    exact_passed = (
        exact_response["success"] is True
        and exact_response["cached"] is True
        and exact_response["cache_type"] == "exact"
        and exact_response["model_used"] is None
        and exact_response["response"]
        == first_response["response"]
    )

    print_result(
        "EXACT CACHE HIT",
        exact_passed,
    )

    # ========================================================
    # TEST 3 - SEMANTIC CACHE HIT
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 3 - SEMANTIC CACHE HIT")
    print("=" * 70)

    semantic_query = (
        "In one short sentence, can you explain "
        "what Python is as a programming language?"
    )

    semantic_response = await service.process(
        message=semantic_query,
        thread_id="chat-cache-test",
    )

    print("\nOriginal query:")
    print(original_query)

    print("\nSemantic query:")
    print(semantic_query)

    print("\nResponse:")
    print(semantic_response)

    print("\nCached:")
    print(semantic_response["cached"])

    print("\nCache type:")
    print(semantic_response["cache_type"])

    print("\nModel used:")
    print(semantic_response["model_used"])

    semantic_passed = (
        semantic_response["success"] is True
        and semantic_response["cached"] is True
        and semantic_response["cache_type"]
        == "semantic"
        and semantic_response["model_used"] is None
        and semantic_response["response"]
        == first_response["response"]
    )

    print_result(
        "SEMANTIC CACHE HIT",
        semantic_passed,
    )

    # ========================================================
    # TEST 4 - WORKER CACHE STATS
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 4 - CACHE STATS FOR THIS WORKER")
    print("=" * 70)

    stats = cache_manager.stats

    print("\nExact Cache:")
    print(
        "Hits:",
        stats["exact"]["hits"],
    )
    print(
        "Misses:",
        stats["exact"]["misses"],
    )
    print(
        "Hit Rate:",
        stats["exact"]["hit_rate"],
    )

    print("\nSemantic Cache:")
    print(
        "Hits:",
        stats["semantic"]["hits"],
    )
    print(
        "Misses:",
        stats["semantic"]["misses"],
    )
    print(
        "Hit Rate:",
        stats["semantic"]["hit_rate"],
    )

    print("\nExpected:")
    print(
        "Exact    -> hits=1, misses=2"
    )
    print(
        "Semantic -> hits=1, misses=1"
    )

    stats_passed = (
        stats["exact"]["hits"] == 1
        and stats["exact"]["misses"] == 2
        and stats["semantic"]["hits"] == 1
        and stats["semantic"]["misses"] == 1
    )

    print_result(
        "WORKER CACHE STATS",
        stats_passed,
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(
        "Cache Miss:",
        "PASS" if miss_passed else "FAIL",
    )

    print(
        "Exact Hit:",
        "PASS" if exact_passed else "FAIL",
    )

    print(
        "Semantic Hit:",
        "PASS" if semantic_passed else "FAIL",
    )

    print(
        "Worker Stats:",
        "PASS" if stats_passed else "FAIL",
    )


if __name__ == "__main__":
    asyncio.run(main())
