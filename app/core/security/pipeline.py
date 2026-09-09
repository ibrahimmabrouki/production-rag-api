# this will include the security pipline that combines all three togther
# so we will have one class that roll them all

from app.core.security.pii_masking import PIIDetector
from app.core.security.output_validation import OutputValidator
from app.core.security.prompt_injection import InputSanitizer


# traceble is used to log the security checks in the Langsmith dashboard.
# Record the execution of this function as a LangSmith trace/run.
from langsmith import traceable

# for example when we all the check_input function: 
# pipeline.check_input("My email is test@gmail.com")

# then: LangSmith can record something conceptually like:
# security_check_input
# │
# ├── Input
# │   └── "My email is test@gmail.com"
# │
# ├── Function execution
# │
# ├── Output
# │   ├── True
# │   ├── "My email is [EMAIL]"
# │   └── ["PII detected and masked: ['email']"]
# │
# └── Execution time

# and this doesn't need to be an LLM call.

# since later what we are going to have => LangSmith trace could look conceptually like:
# API Request
# │
# ├── security_check_input
# │
# ├── RAG retrieval
# │
# ├── LLM call
# │
# └── security_check_output

# This allows you to see where time was spent and what happened at each stage.

class SecurityPipeline:
    """
    Full security pipeline that processes input output.
    This is the single class you wire into your api
    """

    def __init__(self) -> None:
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDetector()
        self.output_validator = OutputValidator()

    # we are using traceble for langsmith to be able to log all these things
    @traceable(name="security_check_input")
    def check_input(self, text: str) -> tuple[bool, str, list[str]]:
        """
        Process input through security checks.
        Returns: (is_allowed, cleaned_text, security_notes)
        """

        notes: list[str] = []

        # Step 1: Check for injection
        is_safe, reason = self.sanitizer.check(text)
        if not is_safe:
            return False, "", [reason]

        # Step 2: Clean the input
        cleaned = self.sanitizer.clean(text)

        # Step 3: Mask PII before it reacheds the LLM
        pii_found = self.pii_detector.detect(cleaned)
        # pii_found is the object returned it is true it contains PII and it will be false if it doesnt contain PII
        if pii_found:
            cleaned = self.pii_detector.mask(cleaned)
            notes.append(f"PII detected and masked: {list(pii_found.keys())}")

        return True, cleaned, notes

    @traceable(name="security_check_output")
    def check_output(self, text: str) -> tuple[str, list[str], bool]:
        """
        Process output through security checks before its returning to the user.
        Returns: (cleaned_text, security_notes, is_safe)
        """

        return self.output_validator.validate(text)
