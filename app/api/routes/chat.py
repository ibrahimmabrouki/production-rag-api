"""
HTTP request
    ↓
validate request
    ↓
call ChatService
    ↓
return ChatResponse


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    return await service.process(body)
    
Then this below is the actual business logic that is handeled in the service
security_pipeline.check_input(...)
cache_manager.get(...)
agent.invoke(...)
cache_manager.set(...)
"""


from fastapi import APIRouter, Depends
from app.dependencies.services import get_chat_service
from app.services.chat_service import ChatService
from app.models.requests import ChatRequest
from app.models.responses import ChatResponse
from app.api.route_classes.metrics_route import MetricsAPIRoute

"""
here we are telling the APIRouter ot use the MetricsAPIRouter which is the custom route class that we created to add additional fucntionality to the router handler 
APIRouter
   ↓
MetricsAPIRoute
   ↓
metrics logic
   ↓
normal FastAPI route processing
   ↓
chat()
"""

router = APIRouter(
    route_class=MetricsAPIRoute
)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    # FastAPI sees Depends(get_chat_service) and automatically calls
    # essentially gives your route access to the shared ChatService that you created during application startup.
) -> ChatResponse:
    """
    Process a chat request.

    FastAPI:
    1. Validates the incoming JSON using ChatRequest.
    2. Injects the shared ChatService from app.state.
    3. Calls the ChatService business logic.
    4. Validates the returned result using ChatResponse.
    """
    result = await service.process(
        message=body.message,
        thread_id=body.thread_id,
    )

    return ChatResponse(**result)
