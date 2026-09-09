"""
Manual tests for ProductionAgent.

Run:

python -m tests.agents.test_agent
"""

from app.core.observability.observability import configure_langsmith

configure_langsmith()

from app.agents.agent import ProductionAgent

def test_primary():
    print("\n--- PRIMARY MODEL ---")

    agent = ProductionAgent()

    result = agent.invoke("What is RAG?")

    print(f"Response: {result['response']}")
    print(f"Model used: {result['model_used']}")
    print(f"Error: {result['error']}")


def test_fallback():
    print("\n--- FALLBACK MODEL ---")

    agent = ProductionAgent()

    class FailingLLM:
        def invoke(self, messages):
            raise Exception("Simulated primary model failure.")

    agent.primary_llm = FailingLLM()

    result = agent.invoke("What is RAG?")

    print(f"Response: {result['response']}")
    print(f"Model used: {result['model_used']}")
    print(f"Error: {result['error']}")


def test_complete_failure():
    print("\n--- PRIMARY + FALLBACK FAILURE ---")

    agent = ProductionAgent()

    class FailingLLM:
        def invoke(self, messages):
            raise Exception("Simulated LLM failure.")

    agent.primary_llm = FailingLLM()
    agent.fallback_llm = FailingLLM()

    result = agent.invoke("What is RAG?")

    print(f"Response: {result['response']}")
    print(f"Model used: {result['model_used']}")
    print(f"Error: {result['error']}")


if __name__ == "__main__":
    test_primary()
    test_fallback()
    test_complete_failure()

    print("\nAll tests completed.")