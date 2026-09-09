"""
This is a test file for the langsmith integration. It sets up the necessary environment variables and runs a simple traceable function to verify that tracing is working correctly.
use the following command to run the test:
python -m tests.monitoring.test_langsmith
"""


from langsmith import Client, traceable
from app.core.config import get_settings
import os

settings = get_settings()

# Make env vars consistent with .env / Settings
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


@traceable(name="langsmith_test")
def test_trace():
    return "LangSmith test successful"


result = test_trace()

Client(api_key=settings.langchain_api_key).flush()

print(result)