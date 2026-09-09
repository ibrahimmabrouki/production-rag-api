"""
Simulation test for the TokenBudget class.

Run:
python -m tests.core.test_token_budget
"""

from app.core.token_budget.budget import TokenBudget
from app.core.token_budget.chat_usage import ChatUsage


def test_token_budget() -> None:
    budget = TokenBudget()

    print("\n--- TOKEN BUDGET TEST ---")

    # --------------------------------------------------
    # TEST 1: Small input
    # --------------------------------------------------

    message = "What is Redis?"

    allowed, estimated_tokens = budget.check_input(message)

    print("\nTest 1: Small input")
    print(f"Message: {message}")
    print(f"Estimated tokens: {estimated_tokens}")
    print(f"Maximum allowed: {budget.max_input_tokens}")
    print(f"Allowed: {allowed}")

    # --------------------------------------------------
    # TEST 2: Large input
    # --------------------------------------------------

    large_message = "hello " * 4000

    allowed, estimated_tokens = budget.check_input(
        large_message
    )

    print("\nTest 2: Large input")
    print(f"Estimated tokens: {estimated_tokens}")
    print(f"Maximum allowed: {budget.max_input_tokens}")
    print(f"Allowed: {allowed}")

    # --------------------------------------------------
    # TEST 3: Chat request allowed
    # --------------------------------------------------

    usage = ChatUsage(
        total_input_tokens=1000,
        total_output_tokens=500,
        total_requests=5,
    )

    allowed, reason = budget.check_chat(
        usage=usage,
        estimated_input_tokens=100,
    )

    print("\nTest 3: Chat request allowed")
    print(f"Current total tokens: {usage.total_tokens}")
    print(f"Current requests: {usage.total_requests}")
    print(f"Allowed: {allowed}")
    print(f"Reason: {reason}")

    # --------------------------------------------------
    # TEST 4: Request limit reached
    # --------------------------------------------------

    usage = ChatUsage(
        total_input_tokens=1000,
        total_output_tokens=500,
        total_requests=budget.max_requests_per_chat,
    )

    allowed, reason = budget.check_chat(
        usage=usage,
        estimated_input_tokens=100,
    )

    print("\nTest 4: Request limit reached")
    print(f"Current requests: {usage.total_requests}")
    print(
        f"Maximum requests: "
        f"{budget.max_requests_per_chat}"
    )
    print(f"Allowed: {allowed}")
    print(f"Reason: {reason}")

    # --------------------------------------------------
    # TEST 5: Chat token limit exceeded
    # --------------------------------------------------

    usage = ChatUsage(
        total_input_tokens=budget.max_chat_tokens - 50,
        total_output_tokens=0,
        total_requests=1,
    )

    allowed, reason = budget.check_chat(
        usage=usage,
        estimated_input_tokens=100,
    )

    print("\nTest 5: Chat token limit exceeded")
    print(f"Current total tokens: {usage.total_tokens}")
    print("New estimated input tokens: 100")
    print(f"Maximum chat tokens: {budget.max_chat_tokens}")
    print(f"Allowed: {allowed}")
    print(f"Reason: {reason}")

    # --------------------------------------------------
    # TEST 6: Record usage
    # --------------------------------------------------

    usage = ChatUsage()

    budget.record_usage(
        usage=usage,
        input_tokens=100,
        output_tokens=50,
    )

    print("\nTest 6: Record usage")
    print(f"Input tokens: {usage.total_input_tokens}")
    print(f"Output tokens: {usage.total_output_tokens}")
    print(f"Total tokens: {usage.total_tokens}")
    print(f"Total requests: {usage.total_requests}")

    # --------------------------------------------------
    # TEST 7: Record another request
    # --------------------------------------------------

    budget.record_usage(
        usage=usage,
        input_tokens=200,
        output_tokens=80,
    )

    print("\nTest 7: Multiple requests")
    print(f"Input tokens: {usage.total_input_tokens}")
    print(f"Output tokens: {usage.total_output_tokens}")
    print(f"Total tokens: {usage.total_tokens}")
    print(f"Total requests: {usage.total_requests}")

    print("\n--- TEST COMPLETED ---")


if __name__ == "__main__":
    test_token_budget()
