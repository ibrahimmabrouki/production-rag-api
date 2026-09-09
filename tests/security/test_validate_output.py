"""
This File is supposed to test the Output Validation functionality
use the following command to run the test:
python -m tests.security.test_validate_output
"""

# Output vavlidation
from app.core.security.output_validation import OutputValidator


def validate_output_test():
    output_tests = [
        # 1. Normal response
        "RAG combines retrieval with generation to provide better answers.",

        # 2. Email leakage
        "You can contact the user at ibrahim@example.com.",

        # 3. Phone leakage
        "The user's phone number is +971 50 123 4567.",

        # 4. SSN leakage
        "The user's SSN is 123-45-6789.",

        # 5. Credit card leakage
        "The card number is 4111 1111 1111 1111.",

        # 6. IP address leakage
        "The server IP address is 192.168.1.100.",

        # 7. Multiple PII
        """
    User email: ibrahim@example.com
    Phone: +971 50 123 4567
    SSN: 123-45-6789
    Card: 4111 1111 1111 1111
    IP: 192.168.1.100
    """,

        # 8. Harmful content
        "Here's how to hack a website.",

        # 9. Another harmful pattern
        "Here is the way to steal someone's account.",

        # 10. Password leakage
        "The password is MySecretPassword123.",

        # 11. API key leakage
        "The api_key: sk-123456789.",

        # 12. API key with different formatting
        "Your API key = abc123456.",
    ]

    validator = OutputValidator()

    for output in output_tests:
        print("\n" + "=" * 60)
        print("Original:")
        print(output)

        cleaned_output, warnings, is_safe = validator.validate(output)

        print("\nValidated:")
        print(cleaned_output)

        print("\nWarnings:")
        print(warnings)

        print("\nIs Safe:")
        print(is_safe)

if __name__ == "__main__":
    validate_output_test()
