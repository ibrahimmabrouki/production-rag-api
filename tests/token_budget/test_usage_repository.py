"""
This file is responsible for testing the usage repository which is responsible for storing and retrieving the chat usage from Redis.
use the following command to run the tests:
python -m tests.token_budget.test_usage_repository
"""



import asyncio

from app.core.token_budget.usage_repository import (
    chat_usage_repository,
)

# this one is responsible for testing the usage repository when we have a new chat and we want to check the usage for the first time
async def test_new_chat() -> None:
    print("\n=== TEST 1: NEW CHAT ===")

    chat_id = "chat-token-test-new"

    # Clean previous test data
    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    usage = await chat_usage_repository.get_usage(chat_id)

    print("Input tokens:", usage.total_input_tokens)
    print("Output tokens:", usage.total_output_tokens)
    print("Total tokens:", usage.total_tokens)
    print("Requests:", usage.total_requests)


# this one is responsible for testing the usage repository when we have a new chat and we want to check the reserve_request method 
# reserve_request is the method that is responsible for checking if the user can make a request or not based on the current usage and the limits set in the TokenBudget class
# it is going to recieve the chat_id, estimated_input_tokens, max_chat_tokens, max_requests_per_chat and it is going to return a tuple of (allowed: bool, reason: str)
async def test_reserve_request() -> None:
    print("\n=== TEST 2: RESERVE REQUEST ===")

    chat_id = "chat-token-test-reserve"

    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    allowed, reason = await chat_usage_repository.reserve_request(
        chat_id=chat_id,
        estimated_input_tokens=100,
        max_chat_tokens=1000,
        max_requests_per_chat=5,
    )

    print("Allowed:", allowed)
    print("Reason:", reason)

    usage = await chat_usage_repository.get_usage(chat_id)

    print("Input tokens:", usage.total_input_tokens)
    print("Output tokens:", usage.total_output_tokens)
    print("Requests:", usage.total_requests)


async def test_record_output() -> None:
    print("\n=== TEST 3: RECORD OUTPUT ===")

    chat_id = "chat-token-test-output"

    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    await chat_usage_repository.reserve_request(
        chat_id=chat_id,
        estimated_input_tokens=100,
        max_chat_tokens=1000,
        max_requests_per_chat=5,
    )

    await chat_usage_repository.record_output_usage(
        chat_id=chat_id,
        output_tokens=200,
    )

    usage = await chat_usage_repository.get_usage(chat_id)

    print("Input tokens:", usage.total_input_tokens)
    print("Output tokens:", usage.total_output_tokens)
    print("Total tokens:", usage.total_tokens)
    print("Requests:", usage.total_requests)


async def test_request_limit() -> None:
    print("\n=== TEST 4: REQUEST LIMIT ===")

    chat_id = "chat-token-test-request-limit"

    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    for request_number in range(1, 5):
        allowed, reason = await chat_usage_repository.reserve_request(
            chat_id=chat_id,
            estimated_input_tokens=10,
            max_chat_tokens=1000,
            max_requests_per_chat=3,
        )

        print(
            f"Request {request_number}:",
            f"allowed={allowed}",
            f"reason={reason}",
        )

    usage = await chat_usage_repository.get_usage(chat_id)

    print("Final requests:", usage.total_requests)


async def test_token_limit() -> None:
    print("\n=== TEST 5: TOKEN LIMIT ===")

    chat_id = "chat-token-test-token-limit"

    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    allowed, reason = await chat_usage_repository.reserve_request(
        chat_id=chat_id,
        estimated_input_tokens=400,
        max_chat_tokens=500,
        max_requests_per_chat=10,
    )

    print("First request:")
    print("Allowed:", allowed)
    print("Reason:", reason)

    allowed, reason = await chat_usage_repository.reserve_request(
        chat_id=chat_id,
        estimated_input_tokens=200,
        max_chat_tokens=500,
        max_requests_per_chat=10,
    )

    print("\nSecond request:")
    print("Allowed:", allowed)
    print("Reason:", reason)

    usage = await chat_usage_repository.get_usage(chat_id)

    print("\nFinal input tokens:", usage.total_input_tokens)
    print("Final requests:", usage.total_requests)


async def test_concurrent_requests() -> None:
    print("\n=== TEST 6: CONCURRENT REQUESTS ===")

    chat_id = "chat-token-test-concurrent"

    key = chat_usage_repository._make_key(chat_id)
    await chat_usage_repository.redis.delete(key)

    async def send_request(request_number: int):
        allowed, reason = await chat_usage_repository.reserve_request(
            chat_id=chat_id,
            estimated_input_tokens=10,
            max_chat_tokens=1000,
            max_requests_per_chat=3,
        )

        print(
            f"Concurrent request {request_number}:",
            f"allowed={allowed}",
            f"reason={reason}",
        )

    await asyncio.gather(
        send_request(1),
        send_request(2),
        send_request(3),
        send_request(4),
        send_request(5),
    )

    usage = await chat_usage_repository.get_usage(chat_id)

    print("\nFinal requests:", usage.total_requests)
    print("Final input tokens:", usage.total_input_tokens)


async def main() -> None:
    await test_new_chat()
    await test_reserve_request()
    await test_record_output()
    await test_request_limit()
    await test_token_limit()
    await test_concurrent_requests()


if __name__ == "__main__":
    asyncio.run(main())