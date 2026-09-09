def normalize_agent_response(response: str | list) -> str:
    """
    Convert an agent/LLM response into plain text.

    LLM providers may return either:
    - a plain string
    - structured content blocks

    ChatService should always receive a plain string.
    """

    if isinstance(response, str):
        return response

    if isinstance(response, list):
        text_parts: list[str] = []

        for block in response:

            if isinstance(block, str):
                text_parts.append(block)

            elif isinstance(block, dict):
                text = block.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

        return "".join(text_parts)

    raise TypeError(
        f"Unsupported agent response type: "
        f"{type(response).__name__}"
    )
