"""
This File is supposed to test the Prompt Injection functionality
use the following command to run the test:
python -m tests.security.test_pii_detector 
"""

# PII TESTS:
from app.core.security.pii_masking import PIIDetector


def piiTests():
    pii_tests = [
        # Email
        "My email is ibrahim@example.com.",
        "Contact john.doe+work@gmail.com for more information.",

        # Phone
        "My phone number is +971 50 123 4567.",
        "Call me at +1-555-123-4567.",
        "My number is 050-123-4567.",

        # SSN
        "My SSN is 123-45-6789.",

        # Credit card
        "My card number is 4111 1111 1111 1111.",
        "Card: 4111-1111-1111-1111.",

        # IP
        "The server IP is 192.168.1.100.",

        # Multiple PII types
        """
    My name is Ibrahim.
    Email: ibrahim@example.com
    Phone: +971 50 123 4567
    SSN: 123-45-6789
    Card: 4111 1111 1111 1111
    IP: 192.168.1.100
    """,

        # No PII
        "What is retrieval augmented generation?",
    ]

    detector = PIIDetector()

    for text in pii_tests:
        print("\nOriginal:")
        print(text)

        print("Detected:")
        print(detector.detect(text))

        print("Masked:")
        print(detector.mask(text))


if __name__ == "__main__":
    piiTests()
