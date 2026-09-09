from typing import Optional
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


# This is the general state for the production agent.
# It is like a Python dictionary that defines the structure of the state
# It will travel through the workflow and be updated by the nodes in the graph

"""
Initial state

messages = [HumanMessage("Hello")]
error = None
retry_count = 0
model_used = None

Then after the Primary LLM node, the state will be updated to:

messages = [HumanMessage("Hello"), AIMessage("This is the response from the primary LLM.")]
error = None
retry_count = 0
model_used = "primary"


=> State Information is shared between the nodes in the graph. The state is passed from one node to another and can be updated by the nodes. The state is also used to determine the next node to execute based on the current state.
"""


class AgentState(TypedDict):
    """
    State for the production agent.
    Uses Annotated with add_messages reducer fo message accumulation.
    """

    # Annotated:
    # Normally we have messages: list[BaseMessage] which means that the messages is a list of BaseMessage objects
    # But we want to accumulate the messages as we go through the graph, so we use Annotated with add_messages reducer
    # so this tells LangGraph: When a node returns new messages, don't simply replace the old messages. Use add_messages to merge them.
    messages: Annotated[list[AnyMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: Optional[str]
