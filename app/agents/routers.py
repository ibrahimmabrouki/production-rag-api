from app.agents.state import AgentState

# This is not a node, it is a decision function that will use the current state to decide what to do next.
# It looks at the state and decides which edge to follow

# so if the primary model does not return an error ther we are done
# if the primary model returns an error and we have not reached the max retries then we will try again with the primary model (retry)
# if the primary model returns an error and we have reached the max retries then we will go to the error handler



def router_after_primary_node(state: AgentState, max_retries: int) -> str:
    """
    Decide  what to do after primary model attempt.
    """
    if state.get("error") is None:
        return "done"

    elif state["retry_count"] <= max_retries:
        return "retry"

    return "fallback"

    # if the fallback model does not return an error then we are done
    # if the fallback model returns an error then we will go to the error handler



def router_after_fallback_node(state: AgentState) -> str:
    """
    Decide what to do after fallback model attempt.
    """
    if state.get("error") is None:
        return "done"
    return "error"
