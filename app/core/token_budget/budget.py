"""
Token budget management.

Responsible for:
- Estimating token usage
- Enforcing per-request input limits
- Enforcing per-chat token limits
- Enforcing per-chat request limits
- Recording usage
"""

from app.core.config import get_settings
from app.core.token_budget.chat_usage import ChatUsage

"""
Token budget should define the application-wide rules/polices
such as: max input tokens, max chat tokens, max requests per chat, etc.
and ChatUsage should define the state of a single chat/session such as: total input tokens, total output tokens, total requests, etc.

Here TokenBudget is just responsible for validation and enforcing the rules and it is statless => it does not keep track of the state of a chat/session
so it does not mutate the ChatUsage object and as you notice below we used "usage = ChatUsage" and not self.usage = ChatUsage

So TokenBudget needs to read the ChatUsage to make the decision, but it doesn't own or store it.
"""


class TokenBudget:
    """
    Defines and enforces token-budget rules.
    """

    def __init__(self) -> None:
        settings = get_settings()

        self.max_input_tokens = settings.token_max_input
        self.max_chat_tokens = settings.token_max_chat
        self.max_requests_per_chat = (
            settings.token_max_requests_per_chat
        )

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in text.

        This is currently an approximation.
        """

        if not text:
            return 0

        return max(
            1,
            int(len(text.split()) * 1.3),
        )

    def check_input(
        self,
        text: str,
    ) -> tuple[bool, int]:
        """
        Check whether one input exceeds the per-request limit.

        Returns:
            (allowed, estimated_tokens)
        """

        estimated_tokens = self.estimate_tokens(text)

        allowed = (
            estimated_tokens
            <= self.max_input_tokens
        )

        return allowed, estimated_tokens

    def check_chat(
        self,
        usage: ChatUsage,
        estimated_input_tokens: int,
    ) -> tuple[bool, str | None]:
        """
        Check whether another request is allowed for this chat.
        """

        if (
            usage.total_requests
            >= self.max_requests_per_chat
        ):
            return (
                False,
                "Maximum requests per chat exceeded.",
            )

        projected_tokens = (
            usage.total_tokens
            + estimated_input_tokens
        )

        if projected_tokens > self.max_chat_tokens:
            return (
                False,
                "Maximum token budget for chat exceeded.",
            )

        return True, None

    def record_usage(
        self,
        usage: ChatUsage,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Record usage after a completed LLM request.
        """

        usage.total_input_tokens += input_tokens
        usage.total_output_tokens += output_tokens
        usage.total_requests += 1


"""
This TokenBudget class is responsible for defining the rules and policies for token usage and request count
This will be the first line of defense to prevent abuse and to enforce the limits => first layer

1- first we need to make sure that the input is within the allowed limits for a single request (max_input_tokens)

2- then we need to make sure that the total usage for the chat is within the allowed limits (max_chat_tokens and max_requests_per_chat)
so in the chat service first we will read the current usage for the chat from Redis using the chat_id passed to the get_usage method of the ChatUsageRepository Object
then we will call the check_chat method of the TokenBudget class to check if the request is allowed or not based on the current usage and the limits set in the TokenBudget class

This layer is useful when we have for example 50 requests as max number or requests per chat and the user has already made 50 requests and now he is trying to make the 51st request => we will deny the request

while in the following case, this layer failes, since we might have concurrent requests from the same user with the same chat_id and they might all pass the check_chat method since they are all reading the same usage from Redis at the same time and they all see that the total_requests is less than max_requests_per_chat
=> they all proceed to make the request and they all update the usage in atomic way

assume the total_requests is 49 
=> request 1 => incremant to 50 
=> request 2 => increment to 51 
=> request 3 => increment to 52
=> this is a problem since we have exceeded the max_requests_per_chat limit and we only depeneded on the first layer 

Here comes the second layer of defense which is the reserve_request 
3- the reserve_request method will handle the race condition atomically but this time before handling any update it will read the current usage from redis in the same atomic operation and then it will enforce the limits and if the request is allowed it will update the usage in Redis in the same atomic operation

Layer 1 — TokenBudget
→ normal policy/pre-check
→ useful for rejecting obviously over-limit requests early
→ not concurrency-safe by itself

Layer 2 — reserve_request()
→ reads current Redis state
→ checks limits
→ updates usage
→ all in one atomic Redis operation

"""
