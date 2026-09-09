"""
Full ChatService token budget integration test.

REAL:
- SecurityPipeline
- ProductionAgent
- CacheManager
- ExactCache
- SemanticCache
- TokenBudget
- ChatUsageRepository
- Redis

Tests:
1. Normal request usage recording
2. Exact cache hit still records usage
3. Request limit
4. Chat token limit
5. Usage isolation between chats

Run:

python -m tests.services.chat.token_budget.test_chat_token_budget
"""

import asyncio

from app.services.chat_service import ChatService
from app.core.security.pipeline import SecurityPipeline
from app.core.cache.cache_manager import CacheManager
from app.agents.agent import ProductionAgent
from app.core.token_budget.budget import TokenBudget
from app.core.token_budget.usage_repository import ChatUsageRepository
from app.core.redis.redis_client import redis_client


# ============================================================
# HELPERS
# ============================================================

def print_result(name: str, passed: bool):
    print(
        f"\n{name}: "
        f"{'PASS' if passed else 'FAIL'}"
    )


async def clear_chat_usage(chat_id: str):
    key = f"token_usage:chat:{chat_id}"
    await redis_client.redis.delete(key)


async def clear_cache():
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


def create_service():

    security_pipeline = SecurityPipeline()
    cache_manager = CacheManager()
    agent = ProductionAgent()
    token_budget = TokenBudget()
    usage_repository = ChatUsageRepository()

    service = ChatService(
        security_pipeline=security_pipeline,
        cache_manager=cache_manager,
        agent=agent,
        token_budget=token_budget,
        chat_usage_repository=usage_repository,
    )

    return (
        service,
        token_budget,
        usage_repository,
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("\n" + "=" * 70)
    print("CHAT SERVICE TOKEN BUDGET TEST")
    print("=" * 70)

    service, token_budget, usage_repository = (
        create_service()
    )

    chat_id = "token-budget-main-chat"

    await clear_chat_usage(chat_id)
    await clear_cache()

    # ========================================================
    # TEST 1 - NORMAL REQUEST
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 1 - NORMAL REQUEST")
    print("=" * 70)

    message = (
        "Explain FastAPI in one short sentence."
    )

    before = await usage_repository.get_usage(
        chat_id
    )

    print("\nUsage before:")
    print(before)

    response = await service.process(
        message=message,
        thread_id=chat_id,
    )

    print("\nResponse:")
    print(response)

    after = await usage_repository.get_usage(
        chat_id
    )

    print("\nUsage after:")
    print(after)

    normal_passed = (
        response["success"] is True
        and after.total_requests == 1
        and after.total_input_tokens > 0
        and after.total_output_tokens > 0
    )

    print_result(
        "NORMAL REQUEST USAGE",
        normal_passed,
    )

    # ========================================================
    # TEST 2 - EXACT CACHE HIT STILL COUNTS
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 2 - CACHE HIT TOKEN USAGE")
    print("=" * 70)

    before_cache_hit = (
        await usage_repository.get_usage(chat_id)
    )

    print("\nUsage before cache hit:")
    print(before_cache_hit)

    cached_response = await service.process(
        message=message,
        thread_id=chat_id,
    )

    print("\nResponse:")
    print(cached_response)

    after_cache_hit = (
        await usage_repository.get_usage(chat_id)
    )

    print("\nUsage after cache hit:")
    print(after_cache_hit)

    cache_passed = (
        cached_response["success"] is True
        and cached_response["cached"] is True
        and cached_response["cache_type"] == "exact"
        and after_cache_hit.total_requests
        == before_cache_hit.total_requests + 1
        and after_cache_hit.total_input_tokens
        > before_cache_hit.total_input_tokens
        and after_cache_hit.total_output_tokens
        > before_cache_hit.total_output_tokens
    )

    print_result(
        "CACHE HIT COUNTS TOKENS",
        cache_passed,
    )

    # ========================================================
    # TEST 3 - REQUEST LIMIT
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 3 - REQUEST LIMIT")
    print("=" * 70)

    request_limit_chat = (
        "token-budget-request-limit"
    )

    await clear_chat_usage(
        request_limit_chat
    )

    request_limit_key = (
        f"token_usage:chat:{request_limit_chat}"
    )

    await redis_client.redis.hset(
        request_limit_key,
        mapping={
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests":
                token_budget.max_requests_per_chat,
        },
    )

    before_limit = (
        await usage_repository.get_usage(
            request_limit_chat
        )
    )

    print("\nUsage before:")
    print(before_limit)

    response = await service.process(
        message="What is Redis?",
        thread_id=request_limit_chat,
    )

    print("\nResponse:")
    print(response)

    after_limit = (
        await usage_repository.get_usage(
            request_limit_chat
        )
    )

    print("\nUsage after:")
    print(after_limit)

    request_limit_passed = (
        response["success"] is False
        and "Maximum requests per chat exceeded"
        in response["error"]
        and after_limit.total_requests
        == before_limit.total_requests
    )

    print_result(
        "REQUEST LIMIT",
        request_limit_passed,
    )

    # ========================================================
    # TEST 4 - CHAT TOKEN LIMIT
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 4 - CHAT TOKEN LIMIT")
    print("=" * 70)

    token_limit_chat = (
        "token-budget-token-limit"
    )

    await clear_chat_usage(
        token_limit_chat
    )

    token_limit_key = (
        f"token_usage:chat:{token_limit_chat}"
    )

    await redis_client.redis.hset(
        token_limit_key,
        mapping={
            "total_input_tokens":
                token_budget.max_chat_tokens,
            "total_output_tokens": 0,
            "total_requests": 0,
        },
    )

    before_token_limit = (
        await usage_repository.get_usage(
            token_limit_chat
        )
    )

    print("\nUsage before:")
    print(before_token_limit)

    response = await service.process(
        message="Explain REST APIs.",
        thread_id=token_limit_chat,
    )

    print("\nResponse:")
    print(response)

    after_token_limit = (
        await usage_repository.get_usage(
            token_limit_chat
        )
    )

    print("\nUsage after:")
    print(after_token_limit)

    token_limit_passed = (
        response["success"] is False
        and "Maximum token budget for chat exceeded"
        in response["error"]
        and after_token_limit.total_tokens
        == before_token_limit.total_tokens
    )

    print_result(
        "CHAT TOKEN LIMIT",
        token_limit_passed,
    )

    # ========================================================
    # TEST 5 - CHAT USAGE ISOLATION
    # ========================================================

    print("\n" + "=" * 70)
    print("TEST 5 - CHAT USAGE ISOLATION")
    print("=" * 70)

    chat_a = "token-budget-chat-a"
    chat_b = "token-budget-chat-b"

    await clear_chat_usage(chat_a)
    await clear_chat_usage(chat_b)

    response_a = await service.process(
        message="What is PostgreSQL?",
        thread_id=chat_a,
    )

    print("\nChat A response:")
    print(response_a)

    usage_a = await usage_repository.get_usage(
        chat_a
    )

    usage_b = await usage_repository.get_usage(
        chat_b
    )

    print("\nChat A usage:")
    print(usage_a)

    print("\nChat B usage:")
    print(usage_b)

    isolation_passed = (
        usage_a.total_requests == 1
        and usage_a.total_tokens > 0
        and usage_b.total_requests == 0
        and usage_b.total_tokens == 0
    )

    print_result(
        "CHAT USAGE ISOLATION",
        isolation_passed,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(
        "Normal request:",
        "PASS" if normal_passed else "FAIL",
    )

    print(
        "Cache hit usage:",
        "PASS" if cache_passed else "FAIL",
    )

    print(
        "Request limit:",
        "PASS"
        if request_limit_passed
        else "FAIL",
    )

    print(
        "Chat token limit:",
        "PASS"
        if token_limit_passed
        else "FAIL",
    )

    print(
        "Chat isolation:",
        "PASS"
        if isolation_passed
        else "FAIL",
    )


if __name__ == "__main__":
    asyncio.run(main())
