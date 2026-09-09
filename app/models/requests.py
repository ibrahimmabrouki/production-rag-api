from pydantic import BaseModel, Field
# BaseModel → base class for creating Pydantic models
# Field → lets you add validation rules and metadata to individual fields


# Because it extends BaseModel, Pydantic automatically:

# Validates the incoming data.
# Checks types.
# Returns validation errors when data is invalid.

class ChatRequest(BaseModel):
    """Incoming request model."""
    
    # The request must contain a message, and it must be a string.
    # The ... means required. => {} is invalid it should be at least {"message": "char"}
    message: str = Field(
        ...,
        # defining the min and max length are the first line of defense
        # and this is for validation 
        min_length=1,
        max_length=10000,
        
        # This below is documentation metadata.
        # FastAPI uses it when generating Swagger/OpenAPI documentation.
        description="The message to be processed by the LLM."
    )

    # The request can optionally provide a conversation/thread ID.
    # if the client sends {"message": "What is RAG?"} => thread_id will be "default"
    thread_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique conversation/thread identifier."
    )

"""
thread_id is the unique identifier for a conversation -chat- or thread
it will be used to track the usage of teokens and requests for that specific conversation/thread.

{
    "message": "What is RAG?",
    "thread_id": "chat-123"
}

"""
