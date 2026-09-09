"""
Application entry point.

Responsibilities:
    - Create the FastAPI application
    - Configure application lifespan
Later we will add additional responsibilities such as:
    - Configure middleware
    - Configure exception handlers
    - Register routers
    
Use the following to start the application: uvicorn app.main:app --reload
Use the following to see the FastAPI documentation: http://localhost:8000/docs
"""

# This is the main router for the routes that we defined in the app/api/routes directory. It will be included in the FastAPI application instance that we are going to create below.
from app.api.router import api_router

from app.core.lifespan import lifespan

# this import will allow us to create the FastAPI application
from fastapi import FastAPI


app = FastAPI(
    # this is the title of the application that appears in the FastAPI documentation (Swagger UI)
    title="Production RAG API",
    # this is the description of the application that appears in the FastAPI documentation (Swagger UI)
    description="Production-ready RAG API",
    # this is the version of the application that appears in the FastAPI documentation (Swagger UI)
    version="1.0.0",
    # here we are connecting the lifespan to the FastAPI application that we already built.
    # so we are telling FastAPI: "Hey, use this lifespan function to manage the startup and shutdown of the application."
    lifespan=lifespan,
)

"""
This will be the final Structure of the application.

Uvicorn
   │
   │ imports
   ↓
app.main
   │
   ├── creates logger
   │
   ├── defines lifespan
   │
   └── creates FastAPI app
          │
          ↓
      FastAPI startup
          │
          ↓
      lifespan()
          │
          ├── "Starting Production API"
          │
          ├── "Production API started successfully"
          │
          ↓
        yield
          │
          ↓
    Application is running
          │
          ├── /health
          ├── /chat
          └── /metrics
          │
          ↓
      CTRL + C
          │
          ↓
      after yield
          │
          ├── "Shutting down..."
          └── "shutdown completed" 
"""


# here we are including the main router that we defined in app/api/router.py
app.include_router(api_router, prefix="/api", tags=["API"])

"""
uvicorn
   ↓
app.main
   ↓
FastAPI()
   ↓
app.include_router(api_router)
   ↓
api_router
   ↓
health.router
   ↓
GET /api/health



GET /api/health => FastAPI app finds health.router in api_router => whcih finds @router.get("/health")
"""
