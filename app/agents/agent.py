"""
This code is to build a production level agent that can handle errors gracefully and retry on failure.

1- What is LangChain?
LangChain is a framework for developing applications powered by language models. It is like a toolbox for building LLM applications.
For Example RAG system needs things like:
- Connect to LLM, Vector Store, Create Embeddings, Retrive documents, Create Prompts, Create Chains, Create Agents, etc.
LangChain provides all these things in a simple and easy to use way. It also provides a way to build your own custom components and integrate them with the existing ones.

                    LANGCHAIN
                        │
        ┌───────────────┼────────────────┐
        │               │                │
      Models          Tools             RAG
        │               │                │
     Gemini          APIs          Retrievers
     OpenAI          Search        Embeddings
     Anthropic       Functions     Vector DB


2- What is LangGraph?
LangGraph solves a different problem -while LangChain gives the components- LangGraph decides which means:
"In what order should these components execute, and what should happen when something goes wrong?"
=> LangGraph is essentially a workflow/state-machine/orchestration framework for building stateful agent systems.

User
  │
  ▼
Primary LLM
  │
  ├── SUCCESS ───────► END
  │
  └── FAILURE
          │
          ▼
      Retry?
       │
       ├── YES ─────► Primary LLM
       │
       └── NO
          │
          ▼
      Fallback LLM
          │
          ├── SUCCESS ──► END
          │
          └── FAILURE
                  │
                  ▼
             Error Handler
                  │
                  ▼
                 END
- State
- Nodes
- Edges
- Conditional routing
- Retries
- Error handling
- Persistence/checkpointing
- Human-in-the-loop
=> Complex workflows


The above architecture is a simple state machine that can be built using LangGraph. The state machine has the following states:
- Primary LLM: The primary language model that is used to process the user's message.
- Fallback LLM: The secondary language model that is used as a backup when the primary model fails.
- Error Handler: The component that handles errors and provides a graceful error message.

3- What is the difference between LangChain and LangGraph?
LangChain = the parts (components) of the system
LangGraph = the glue (workflow/state-machine/orchestration) that connects the parts together

4- How they work together in this code below?
we have: self.primary_llm = ChatGoogleGenerativeAI(...) and LangGraph: graph = StateGraph(AgentState)

                 YOUR APPLICATION
                       │
                       ▼
                  LANGGRAPH
               controls workflow
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
      LANGCHAIN                 LANGCHAIN
     Primary Gemini            Fallback Gemini
          │                         │
          └────────────┬────────────┘
                       ▼
                     LLM
Note: And LangSmith sits alongside them for observability

5- Why do we need a state machine for a production agent?
- Because we need to handle errors gracefully and retry on failure => more complicated and not just the following:
Question => Retriever => Prompt => LLM => Answer

"""

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.agents.state import AgentState
from app.agents.nodes import call_primary_node, try_fallback_node, handle_error_node
from app.agents.routers import router_after_primary_node, router_after_fallback_node
from app.core.config import get_settings

from app.core.monitoring.metrics import metrics
from app.core.monitoring.logging import get_logger

logger = get_logger(__name__)

class ProductionAgent:
    """
    Production LangGraph agent with:
    -Retry on failure (model fallback)
    -Graceful error handling
    -langsmith tracing
    """

    def __init__(self):

        settings = get_settings()
        self.settings = settings

        

        # print("Tracing:", self.settings.langchain_tracing_v2)
        # print("API key exists:", bool(self.settings.langchain_api_key))
        # print("Project:", self.settings.langchain_project)

        self.primary_llm = ChatGoogleGenerativeAI(
            model=self.settings.primary_model,
            timeout=30,
            max_retries=0,
            api_key=self.settings.gemini_api_key
        )

        self.fallback_llm = ChatGoogleGenerativeAI(
            # model=settings.fallback_model
            model=self.settings.primary_model,
            timeout=30,
            max_retries=0,
            api_key=self.settings.gemini_api_key
        )

        self.max_retries = self.settings.max_retries
        self.graph = self._build_graph()

    def _build_graph(self):
        """
        Build the LangGraph state machine.
        """

        # We are going to have three nodes in the graph: process, fallback, and error. Each node will have a function that will be executed when the graph reaches that node. The functions will take the current state as input and return the updated state as output.

        # This is the code that will be executed when the graph reaches the process node.
        # It will recieve the current state
        def call_primary(state: AgentState) -> dict:
            """
            Try to process the message with the primary model.
            """
            return call_primary_node(state, self.primary_llm)

        # The below function is the code that will be executed when the graph reaches the fallback node. It will recieve the current state and try to process the message with the fallback model. If the fallback model fails, it will return a new state with the error message and model_used as empty string. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.
        def try_fallback(state: AgentState) -> dict:
            """
            Fallback to secondary model.
            """
            return try_fallback_node(state, self.fallback_llm)

        # The below function is the code that will be executed when the graph reaches the error node. It will recieve the current state and return a graceful error message. The new state will be passed to the next node in the graph and this will be decides based on the route and edges.
        def handle_error(state: AgentState) -> dict:
            """
            Return a graceful error message.
            """
            return handle_error_node(state)

        # This is not a node, it is a decision function that will use the current state to decide what to do next.
        # It looks at the state and decides which edge to follow

        # so if the primary model does not return an error ther we are done
        # if the primary model returns an error and we have not reached the max retries then we will try again with the primary model (retry)
        # if the primary model returns an error and we have reached the max retries then we will go to the error handler
        def router_after_process(state: AgentState) -> str:
            """
            Decide  what to do after primary model attempt.
            """
            return router_after_primary_node(state, self.max_retries)

        # if the fallback model does not return an error then we are done
        # if the fallback model returns an error then we will go to the error handler
        def route_after_fallback(state: AgentState) -> str:
            """
            Decide what to do after fallback model attempt.
            """
            return router_after_fallback_node(state)

        # Here we are building the state graph for the agent. The graph needs to be built in the constructor because we need to have access to the primary and fallback llm instances which are created in the constructor.
        graph = StateGraph(AgentState)

        # Create a node called process and when the graph reaches this node, excute call_primary function.
        graph.add_node("process", call_primary)

        # Create a node called fallback and when the graph reaches this node, excute try_fallback function.
        graph.add_node("fallback", try_fallback)

        # Create a node called error and when the graph reaches this node, excute handle_error function.
        graph.add_node("error", handle_error)

        # here we are adding the edges to the graph, The edges represent the transitions between the states. The edges are defined by the router functions that we defined above. The router functions take the current state as input and return the next state as output.
        # first the start node is process (which is the initial state that reference the call_primary), then we will go to the router_after_process which defines what to do next based on the state of the call_primary
        # if the call_primary returns an error and we have not reached the max retries then we will go to the fallback node (which is the try_fallback function), then we will go to the route_after_fallback which defines what to do next based on the state of the try_fallback)
        # if the try_fallback returns an error then we will go to the error node (which is the handle_error function) and we are done. If the try_fallback does not return an error then we are done.

        # This means that when the graph starts, it will go to the process node first
        graph.add_edge(START, "process")

        graph.add_conditional_edges(
            "process",

            # After process finishes, call router_after_process to know what to do next. router_after_process will return either "done", "fallback", or "error" based on the state of the process_message.
            router_after_process,
            {
                # No error => DONE => END
                "done": END,
                # If there is an error and we haven't reached the max retries, go to the fallback node
                "retry": "process",
                # If there is an error and we have reached the max retries, go to the error node
                "fallback": "fallback",
            }
        )

        """
                     process (update the state that will be passed to router to decide what is the next node)
                        │
                        ▼
                router_after_process
              /         |          \
             /          |           \
          done       fallback      error
           │            │            │
           ▼            ▼            ▼
          END        fallback       error
                        │
                        ▼
                     router
                    /     \
                done     error
                 │         │
                 ▼         ▼
                END      error
        """

        graph.add_conditional_edges(
            "fallback",
            route_after_fallback,
            {
                # No error => DONE => END
                "done": END,
                # If there is an error, go to the error node
                "error": "error"
            }
        )

        # To get an executable graph
        graph.add_edge("error", END)

        return graph.compile()

    @traceable(name="production_agent_invoke")
    def invoke(self, message: str) -> dict:
        """
        Invoke the agent with a message.
        Returns: {"response": str, "model_used": str, "error": Optional[str]}

        """

        # we are invoking the graph with the created initial state
        result = self.graph.invoke({
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": None
        })
        # invoke() => START => process => Gemini => success => END

        """
        The result for example: 
        {
          "messages": [
            HumanMessage("What is RAG?"),
            AIMessage("RAG stands for...")
          ],
          "error": None,
          "retry_count": 0,
          "model_used": "primary"
        }
        """

        return {
            "response": result["messages"][-1].content,
            "model_used": result.get("model_used", "unknown"),
            "error": result.get("error")
        }


"""
START
  ↓
Primary LLM
  ↓
Success ───────────────→ END
  │
Failure
  ↓
Retry Primary
  ↓
Success ───────────────→ END
  │
Failure
  ↓
... retry until limit ...
  ↓
Fallback LLM
  ↓
Success ───────────────→ END
  │
Failure
  ↓
Error Handler
  ↓
END
"""
