"""
This file is going to include the lifespan, which is going to be used by the FastAPI app to manage the startup and the shutdown events of the application.
"""
from app.agents.agent import ProductionAgent
from app.services.chat_service import ChatService
from app.core.token_budget.budget import TokenBudget
from app.core.cache.cache_manager import CacheManager
from app.core.security.pipeline import SecurityPipeline
from app.core.token_budget.usage_repository import ChatUsageRepository
from fastapi import FastAPI

# this will allow us to create asynchronous manager which will be used to manage the application lifespan (startup and shutdown)
from contextlib import asynccontextmanager

# @asynccontextmanager
# async def lifespan(app):
#     # startup

#     yield

#     # shutdown

# The code before yield runs during application startup.

# The code after yield runs during application shutdown.


# we previously built centralized logging, so we're using that instead of creating a new logger directly inside main.py
from app.core.monitoring.logging import get_logger


logger = get_logger()
# here we are defining the lifespan of the application, which is a modern FastAPI pattern that replaces the older @app.on_event("startup") and @app.on_event("shutdown") decorators. This allows us to manage the startup and shutdown processes of the application in a more structured way.
# @asynccontextmanager: this tells Python: Treat this function as an asynchronous context manager.

"""
- This application life span is responsible for managing the startup and shutdown of the application. It is a modern FastAPI pattern that replaces the older @app.on_event("startup") and @app.on_event("shutdown") decorators. This allows us to manage the startup and shutdown processes of the application in a more structured way.
- Intializing the Shared dependencies and resources that are used by the application:
1-Cache, 
2-Monitoring,
3-SecurityPipeline
4-TokenBudget 
5-ProductionAgent
=> create the ChatService and inject the above dependencies into it.
6-Database. 
7-RetrievalSystem. 
8-ChatSystem.
These are all initialized during the startup phase of the application.
Then store them in the application state so that they can be accessed by the endpoints and services during the lifetime of the application.

since These objects are shared across the application <=> Application-Level Objects => we should not initilize them on every HTTP request
especially for the ProductionAgent which is a heavy object that takes time due to Creating the LLM clients adn compiling the graph
"""


@asynccontextmanager
# async def This means the function is asynchronous, FastAPI itself is asynchronous, so lifecycle operations can perform things like: await database.connect(), await client.close()
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown.
    """

    # Startup
    # Everything before yield is executed when FastAPI starts.
    logger.info("Starting Production API")

    # Initialize application components and dependencies.
    logger.info("Initializing application components and dependencies.")
    app.state.security_pipeline = SecurityPipeline()
    app.state.cache_manager = CacheManager()
    app.state.token_budget = TokenBudget()
    app.state.chat_usage_repository = ChatUsageRepository()
    app.state.agent = ProductionAgent()

    app.state.chat_service = ChatService(
        security_pipeline=app.state.security_pipeline,
        cache_manager=app.state.cache_manager,
        agent=app.state.agent,
        token_budget=app.state.token_budget,
        chat_usage_repository=app.state.chat_usage_repository,
    )

    """
    Initialize application components and dependencies.
    Starting Production API
        ↓
    Initialize cache
        ↓
    Initialize agent
        ↓
    Initialize monitoring
        ↓
    Initialize token budget
        ↓
    Initialize security pipeline
        ↓
    Initialize chat service
        ↓
    Initialize database
        ↓
    Production API started successfully
    
    If initialization fails before the success message, the application won't finish starting
    """

    logger.info("Production API started successfully")

    # this is the key line we can think of it as a "Pause" in the lifespan of the application.
    # The application will continue to run and handle requests until it is shut down. When the application is shutting down, the code after yield will be executed.
    # here the applicaiton is ready to serve requests:
    # GET /health
    # POST /chat
    # GET /metrics
    # ...
    yield

    # Shutdown
    logger.info("Shutting down Production API")

    # here after the yeild we need to close the application resoures:
    # Close resources
    # Flush data
    # Cleanup

    # Something like the follonwing:
    # await database.close()
    # await redis.close()
    logger.info("Production API shutdown completed")


# this one will create our actual FastAPI application instance.
# Everything else in your API will eventually attach to this object.
"""
For example: 
app
 │
 ├── routes
 ├── middleware
 ├── exception handlers
 └── lifespan 
"""


"""
4-MetricsCollector: unecessary to be initialized here since it is already initialized in the metrics.py file as a singleton object
"""
