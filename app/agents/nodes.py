
from app.agents.state import AgentState
from langchain_core.messages import AIMessage

"""
Now we need to add the add the metrics Related to the LLM these metrics are: 
- LLM_REQUESTS_TOTAL (added in this file <=> nodes.py)
- LLM_LATENCY (added in this file <=> nodes.py)
- LLM_ERRORS_TOTAL (added in this file <=> nodes.py)

- LLM_INPUT_TOKENS_TOTAL
- LLM_OUTPUT_TOKENS_TOTAL
The above two metrics are updated through the same helper method record_llm_tokens() which is called in the nodes.py file after the LLM response.

- TOKEN_LIMIT_EXCEEDED_TOTAL (added in chat_service.py)


LLM_REQUESTS_TOTAL: This metric will be incremented every time a request is made to the LLM, regardless of whether it is successful or not. It will have tags for model_name.
Primary attempt  → +1
Primary retry    → +1
Primary retry    → +1
Fallback attempt → +1
===> So one user request could legitimately produce: LLM_REQUESTS_TOTAL = 4, because the metric measures actual LLM calls, not API requests.

LLM_LATENCY: This metric will be a histogram that measures the latency of LLM requests. It will have tags for model_name
so we will measure the time taken for each LLM request and record it in the histogram. This will help us understand the performance of the LLM and identify any potential bottlenecks.

LLM_ERRORS_TOTAL: This metric will be incremented every time an error occurs during an LLM request. It will have tags for model_name and error_type. The error_type will be the type of the exception that was raised during the LLM request. This will help us understand the types of errors that are occurring and identify any potential issues with the LLM.

"""
from app.core.monitoring.metrics import metrics
from app.core.monitoring.logging import get_logger

logger = get_logger(__name__)


# We are going to have three nodes in the graph: process, fallback, and error. Each node will have a function that will be executed when the graph reaches that node. The functions will take the current state as input and return the updated state as output.

# This is the code that will be executed when the graph reaches the process node.
# It will recieve the current state


def call_primary_node(state: AgentState, primary_llm) -> dict:
    """
    Try to process the message with the primary model.
    """
    try:

        # Record every real attempt to call the primary LLM.
        # This is placed before invoke() so failed attempts are counted too.
        try:
            metrics.record_llm_request(model=primary_llm.model)

        except Exception:
            # Metrics must never prevent the real LLM call.
            logger.exception(
                "Failed to record LLM request metric for primary model"
            )

        # taking all the messages from the current state and passing them to the primary model to get a response.
        # for example if the current state[messages] = [HumanMessage(What is RAG?)], then the primary model will return a response like AIMessage(RAG is Retrieval Augmented Generation)
        with metrics.track_llm_latency(model=primary_llm.model):
            response = primary_llm.invoke(state["messages"])

        # print("USAGE METADATA:", getattr(response, "usage_metadata", None))

        usage = getattr(response, "usage_metadata", None)

        if usage:
            try:
                metrics.record_llm_tokens(
                    model=primary_llm.model,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
            except Exception:
                logger.exception(
                    "Failed to record LLM tokens metric for primary model"
                )

        # Then we return a new state with the updated messages, error, and model_used. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.
        return {
            "messages": [response],
            "error": None,
            "model_used": "primary"
        }
    # If the primary model fails, we catch the exception and return a new state with the error message, incremented retry_count, and model_used as empty string. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.
    except Exception as e:
        try:
            metrics.record_llm_error(
                model=primary_llm.model,
                error_type=type(e).__name__
            )
        except Exception:
            logger.exception(
                "Failed to record LLM error metric for primary model"
            )
        return {
            "error": str(e),
            "retry_count": state["retry_count"] + 1,
            "model_used": None,
        }

# LangGraph then applies those updates to the graph state.
# The graph state is updated with the new messages, error, and model_used.

# The below function is the code that will be executed when the graph reaches the fallback node. It will recieve the current state and try to process the message with the fallback model. If the fallback model fails, it will return a new state with the error message and model_used as empty string. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.


def try_fallback_node(state: AgentState, fallback_llm) -> dict:
    """
    Fallback to secondary model.
    """
    try:
        # Record every real attempt to call the fallback LLM.
        try:
            metrics.record_llm_request(
                model=fallback_llm.model
            )
        except Exception:
            logger.exception(
                "Failed to record fallback LLM request metric"
            )

        with metrics.track_llm_latency(model=fallback_llm.model):
            response = fallback_llm.invoke(state["messages"])

        usage = getattr(response, "usage_metadata", None)
        if usage:
            try:
                metrics.record_llm_tokens(
                    model=fallback_llm.model,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
            except Exception:
                logger.exception(
                    "Failed to record LLM tokens metric for fallback model"
                )

        return {
            "messages": [response],
            "error": None,
            "model_used": "fallback"
        }
    except Exception as e:
        try:
            metrics.record_llm_error(
                model=fallback_llm.model,
                error_type=type(e).__name__
            )
        except Exception:
            logger.exception(
                "Failed to record LLM error metric for fallback model"
            )
        return {
            "error": str(e),
            "model_used": None
        }

# The below function is the code that will be executed when the graph reaches the error node. It will recieve the current state and return a graceful error message. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.


def handle_error_node(state: AgentState) -> dict:
    """
    Return a graceful error message.
    """
    return {
        "messages": [
            AIMessage(content=("I'm sorry, but I having issues processing you request right now. Please try again later or contact support if the issue persists.")
                      )
        ],
        "model_used": None,
        "error": state.get("error", "Unknown error")
    }
