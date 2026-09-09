"""
The purpose of this file is to let the routes/services access the objects we sotred in the application state during the startup phase of the application.

since there are some objects that are shared across the FastAPI application => they are application-level objects => we should not initilize them on every HTTP request
so, what we do is to initialize them during the startup phase of the application, and then store them in the application state so that they can be accessed by the endpoints and services during the lifetime of the application.

these objects are:)
1-Cache, 
2-Monitoring,
3-SecurityPipeline
4-TokenBudget 
5-ProductionAgent
6-Database. 
7-RetrievalSystem. 
8-ChatSystem.

so, this file will organize how we use these reusable dependencies:

instead of doing this in every endpoint:
request.app.state.security_pipeline
request.app.state.cache_manager

we can do this in every endpoint:
defining a wrapper function that will return the object we want from the application state.

then later in the route what we can do is: 
agent: ProductionAgent = Depends(get_agent) 
and this is going to be better since we are injecting the dependency into the route rother than creating a new instance of the ProductionAgent in every route.

"""

from fastapi import Request

from app.core.security.pipeline import SecurityPipeline
from app.core.cache.cache_manager import CacheManager
from app.core.monitoring.metrics import MetricsCollector
from app.core.token_budget.budget import TokenBudget
from app.services.chat_service import ChatService
from app.agents.agent import ProductionAgent


# This method is responsible for returning the SecurityPipline object from the request
def get_security_pipeline(request: Request) -> SecurityPipeline:
    return request.app.state.security_pipeline


# This method is responsible for returning the CacheManager object from the request
def get_cache_manager(request: Request) -> CacheManager:
    return request.app.state.cache_manager


# This method is responsible for returning the MetricsCollector object from the request
def get_metrics(request: Request) -> MetricsCollector:
    return request.app.state.metrics


# This method is responsible for returning the TokenBudget object from the request
def get_token_budget(request: Request) -> TokenBudget:
    return request.app.state.token_budget


# This method is responsible for returning the ProductionAgent object from the request
def get_agent(request: Request) -> ProductionAgent:
    return request.app.state.agent

# This method is responsible for returning the ChatService object from the request


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service
