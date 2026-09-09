"""
Chat token usage state.

Responsible for:
- Tracking total input tokens
- Tracking total output tokens
- Tracking total requests
- Calculating total token usage

This class represents the state of one chat/session.
It does not enforce token limits.
"""

from dataclasses import dataclass


@dataclass
class ChatUsage:
    """
    Token usage state for a single chat/session.
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0

    @property
    def total_tokens(self) -> int:
        """
        Return the total tokens used by the chat.
        """

        return (
            self.total_input_tokens
            + self.total_output_tokens
        )