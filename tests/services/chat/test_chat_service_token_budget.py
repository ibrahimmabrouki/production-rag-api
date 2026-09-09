"""
This file is test script to test the chat service with token budget
use the following command to run the test:
python -m tests.services.chat.test_chat_service_token_budget
"""

import asyncio

from app.services.chat_service import ChatService
from app.core.security.pipeline import SecurityPipeline
from app.core.cache.cache_manager import CacheManager
from app.agents.agent import ProductionAgent
from app.core.token_budget.budget import TokenBudget
from app.core.token_budget.usage_repository import ChatUsageRepository


async def main():
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

    print("\n==============================")
    print("TEST 1 - NORMAL TOKEN REQUEST")
    print("==============================")

    thread_id = "chat-token-normal"

    response = await service.process(
        message="Explain what RAG is in one short sentence.",
        thread_id=thread_id,
    )

    print("Response:")
    print(response)

    usage = await usage_repository.get_usage(thread_id)

    print("\nRedis usage:")
    print("Input tokens:", usage.total_input_tokens)
    print("Output tokens:", usage.total_output_tokens)
    print("Total tokens:", usage.total_tokens)
    print("Requests:", usage.total_requests)

    print("\n==============================")
    print("TEST 2 - INPUT TOKEN LIMIT")
    print("==============================")

    thread_id = "chat-token-input-limit"

    large_message = "hello " * (
        token_budget.max_input_tokens + 1000
    )

    response = await service.process(
        message=large_message,
        thread_id=thread_id,
    )

    print("Response:")
    print(response)

    usage = await usage_repository.get_usage(thread_id)

    print("\nRedis usage:")
    print("Total tokens:", usage.total_tokens)
    print("Requests:", usage.total_requests)

    print("\n==============================")
    print("TEST 3 - LAYER 1 REQUEST LIMIT")
    print("==============================")

    thread_id = "chat-token-layer1"

    key = usage_repository._make_key(thread_id)

    await usage_repository.redis.hset(
        key,
        mapping={
            "total_input_tokens": 100,
            "total_output_tokens": 100,
            "total_requests":
                token_budget.max_requests_per_chat,
        },
    )

    response = await service.process(
        message="What is FastAPI?",
        thread_id=thread_id,
    )

    print("Response:")
    print(response)

    print("\n==============================")
    print("TEST 4 - LAYER 1 TOKEN LIMIT")
    print("==============================")

    thread_id = "chat-token-layer1-limit"

    key = usage_repository._make_key(thread_id)

    await usage_repository.redis.hset(
        key,
        mapping={
            "total_input_tokens":
                token_budget.max_chat_tokens,
            "total_output_tokens": 0,
            "total_requests": 1,
        },
    )

    response = await service.process(
        message="Explain Redis.",
        thread_id=thread_id,
    )

    print("Response:")
    print(response)

    print("\n==============================")
    print("TEST 5 - LAYER 2 CONCURRENCY")
    print("==============================")

    thread_id = "chat-token-layer2"

    key = usage_repository._make_key(thread_id)

    await usage_repository.redis.delete(key)

    await usage_repository.redis.hset(
        key,
        mapping={
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests":
                token_budget.max_requests_per_chat - 1,
        },
    )

    async def send_request(name: str):
        result = await service.process(
            message=f"Explain Python briefly for {name}.",
            thread_id=thread_id,
        )

        print(f"\n{name}:")
        print(result)

    await asyncio.gather(
        send_request("request-A"),
        send_request("request-B"),
    )

    usage = await usage_repository.get_usage(thread_id)

    print("\nFinal Redis usage:")
    print("Requests:", usage.total_requests)
    print(
        "Maximum allowed:",
        token_budget.max_requests_per_chat,
    )

    print("\n==============================")
    print("TEST 6 - CACHE HIT TOKEN USAGE")
    print("==============================")

    thread_id = "chat-token-cache-hit"

    # Clean previous token usage for this thread
    key = usage_repository._make_key(thread_id)
    await usage_repository.redis.delete(key)

    message = "Explain artificial intelligence in one short sentence."

    # First request:
    # Expected to miss cache and generate/store the response.
    first_response = await service.process(
        message=message,
        thread_id=thread_id,
    )

    usage_after_first = await usage_repository.get_usage(
        thread_id
    )

    print("\nFirst request:")
    print("Cached:", first_response["cached"])
    print("Input tokens:", usage_after_first.total_input_tokens)
    print("Output tokens:", usage_after_first.total_output_tokens)
    print("Requests:", usage_after_first.total_requests)

    # Second request:
    # Same message should now hit the exact cache.
    second_response = await service.process(
        message=message,
        thread_id=thread_id,
    )

    usage_after_second = await usage_repository.get_usage(
        thread_id
    )

    print("\nSecond request:")
    print("Cached:", second_response["cached"])
    print("Cache type:", second_response["cache_type"])

    print("\nUsage after cache hit:")
    print("Input tokens:", usage_after_second.total_input_tokens)
    print("Output tokens:", usage_after_second.total_output_tokens)
    print("Total tokens:", usage_after_second.total_tokens)
    print("Requests:", usage_after_second.total_requests)

    print("\nUsage increase caused by cache hit:")
    print(
        "Input tokens added:",
        usage_after_second.total_input_tokens
        - usage_after_first.total_input_tokens,
    )
    print(
        "Output tokens added:",
        usage_after_second.total_output_tokens
        - usage_after_first.total_output_tokens,
    )
    print(
        "Requests added:",
        usage_after_second.total_requests
        - usage_after_first.total_requests,
    )


if __name__ == "__main__":
    asyncio.run(main())
