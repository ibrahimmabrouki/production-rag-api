"""
This is the Central API router
Its responsibility is to collect all API route modules and combine them into one router:

                    api_router
                        │
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
       chat.router  health.router  metrics.router
          │             │             │
        /chat         /health       /metrics

for example app/api/routes/chat.py defines the chat.router which handles the /chat endpoint.
The route handles HTTP. The service handles the actual application logic.

Eventually:
HTTP Request
     ↓
chat.py
     ↓
ChatService
     ↓
Security
     ↓
Cache
     ↓
RAG
     ↓
LLM
     ↓
Response

"""


from fastapi import APIRouter

from app.api.routes import chat, health, metrics

api_router = APIRouter()

# each of the follwing line is: Add all endpoints from the health router to the main API router.

"""
This one includes the chat router with its custom MetricsAPIRoute 

main.py
  ↓
api/router.py
  ↓
chat.router
  ↓
MetricsAPIRoute
  ↓
/chat

while: 

health.router
  ↓
normal APIRoute

metrics.router
  ↓
normal APIRoute
"""
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(metrics.router, tags=["Metrics"])
