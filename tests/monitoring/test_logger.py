"""
This File is supposed to test the Prompt Injection functionality
use the following command to run the test:
python -m tests.monitoring.test_logger
"""
import json
from app.core.monitoring.logging import get_logger


logger = get_logger("logger-test")


# Test 1: Basic INFO log
logger.info("Application started")


# Test 2: WARNING log
logger.warning("This is a warning")


# Test 3: ERROR log
logger.error("Something went wrong")


# Test 4: Structured data
logger.info(
    "LLM request completed",
    extra={
        "extra_data": {
            "latency_ms": 1250,
            "input_tokens": 100,
            "output_tokens": 250,
        }
    },
)


# Test 5: Cache event
logger.info(
    "Cache hit",
    extra={
        "extra_data": {
            "cache_type": "exact",
            "query": "What is RAG?",
        }
    },
)
