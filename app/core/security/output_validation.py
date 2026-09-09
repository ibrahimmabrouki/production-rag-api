"""
Security utilities for the application.

This layer validates LLM output before returning it to the client.

Responsibilities:
1. Detect and mask PII leakage.
2. Detect potentially harmful or sensitive content.
"""

import re

from app.core.security.pii_masking import PIIDetector


class OutputValidator:
    """
    Validates LLM output before returning it to the client.

    Checks for:
    - PII leakage
    - Sensitive information
    - Potentially harmful content
    """

    HARMFUL_PATTERNS = [
        re.compile(
            r"here(?:'s| is)\s+(?:how|the way)\s+to\s+"
            r"(?:hack|steal|attack)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bpassword\s+(?:is|:)\s+\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bapi[_\s-]?key\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ]

    def __init__(self) -> None:
        self.pii_detector = PIIDetector()

    def validate(self, output: str) -> tuple[str, list[str], bool]:
        """
        Validate and clean LLM output.

        Returns:
            A tuple containing:
            - cleaned output
            - list of warnings
            - boolean indicating if the output is safe
        """

        warnings: list[str] = []
        is_safe = True

        # 1. Detect and mask PII
        pii_found = self.pii_detector.detect(output)

        if pii_found:
            output = self.pii_detector.mask(output)

            warnings.append(
                f"PII masked in output: {list(pii_found.keys())}"
            )

        # 2. Check for harmful or sensitive content
        for pattern in self.HARMFUL_PATTERNS:
            if pattern.search(output):
                output = "Response blocked: potentially harmful content."
                warnings.append("Potentially harmful content blocked.")
                is_safe = False
                break

        return output, warnings, is_safe


# LLM Output
#     ↓
# PII Detection
#     ↓
# PII found?
#     ├── Yes → Mask PII
#     └── No
#     ↓
# Harmful/Sensitive Content Check
#     ↓
# Problem found?
#     ├── Yes → Block response
#     └── No
#     ↓
# Return safe output
