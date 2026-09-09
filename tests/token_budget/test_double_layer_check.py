"""
Test the two-layer token budget protection.

Layer 1:
TokenBudget.check_chat()

Layer 2:
ChatUsageRepository.reserve_request()

Run:
python -m tests.token_budget.test_double_layer_check
"""

import asyncio

from app.core.token_budget.budget import TokenBudget
from app.core.token_budget.usage_repository import (
    chat_usage_repository,
)


async def test_double_layer_check() -> None:
    print("\n--- DOUBLE LAYER CHECK TEST ---")

    budget = TokenBudget()

    chat_id = "chat-double-layer-test"

    key = chat_usage_repository._make_key(chat_id)

    # Clean old test data
    await chat_usage_repository.redis.delete(key)

    # --------------------------------------------------
    # PREPARE STATE
    # --------------------------------------------------

    # We want:
    # current requests = max_requests - 1
    #
    # Example:
    # max = 50
    # current = 49

    current_requests = (
        budget.max_requests_per_chat - 1
    )

    await chat_usage_repository.redis.hset(
        key,
        mapping={
            "total_input_tokens": 100,
            "total_output_tokens": 100,
            "total_requests": current_requests,
        },
    )

    print("\nInitial state:")
    print(f"Current requests: {current_requests}")
    print(
        f"Maximum requests: "
        f"{budget.max_requests_per_chat}"
    )

    # --------------------------------------------------
    # TWO CONCURRENT REQUESTS
    # --------------------------------------------------

    async def process_request(
        request_name: str,
    ) -> None:

        print(f"\n{request_name} started")

        # ----------------------------------------------
        # LAYER 1
        # ----------------------------------------------

        usage = await chat_usage_repository.get_usage(
            chat_id
        )

        allowed, reason = budget.check_chat(
            usage=usage,
            estimated_input_tokens=10,
        )

        print(
            f"{request_name} Layer 1 -> "
            f"requests read: {usage.total_requests}"
        )
        print(
            f"{request_name} Layer 1 -> "
            f"allowed: {allowed}"
        )

        if not allowed:
            print(
                f"{request_name} stopped at Layer 1: "
                f"{reason}"
            )
            return

        # Force both requests to have time to pass
        # Layer 1 before reaching Layer 2.
        await asyncio.sleep(0.1)

        # ----------------------------------------------
        # LAYER 2
        # ----------------------------------------------

        allowed, reason = (
            await chat_usage_repository.reserve_request(
                chat_id=chat_id,
                estimated_input_tokens=10,
                max_chat_tokens=budget.max_chat_tokens,
                max_requests_per_chat=(
                    budget.max_requests_per_chat
                ),
            )
        )

        print(
            f"{request_name} Layer 2 -> "
            f"allowed: {allowed}"
        )

        print(
            f"{request_name} Layer 2 -> "
            f"reason: {reason}"
        )

    # Run both requests concurrently
    await asyncio.gather(
        process_request("Request 1"),
        process_request("Request 2"),
    )

    # --------------------------------------------------
    # FINAL STATE
    # --------------------------------------------------

    usage = await chat_usage_repository.get_usage(
        chat_id
    )

    print("\nFinal state:")
    print(
        f"Total requests: "
        f"{usage.total_requests}"
    )

    print(
        f"Maximum requests: "
        f"{budget.max_requests_per_chat}"
    )

    print("\n--- TEST COMPLETED ---")


if __name__ == "__main__":
    asyncio.run(
        test_double_layer_check()
    )
