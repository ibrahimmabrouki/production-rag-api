"""
This containes health-related endpoints

for example: GET /health
its purpose is to tell if the API process alive and capable of serving requests

later we could have 
/health
/health/live
/health/ready

Can the application actually serve traffic?
Are required dependencies available?

"""

# here will be defined the ac
# from fastapi import APIRouter

# router = APIRouter()

# @router.get("/health")
# async def health():
#     return {"status": "healthy"}

# This code below is used for testing:
# This allow us to organize the health-related edpoints in one single file, and then we can include this router in the main API router in app/api/router.py
# ===> APIRouter allows us to organize endpoints into separate modules.
# include means that we are including the routes defined in this router into the main API router, so that they can be accessed by the clients.
from fastapi import APIRouter, Depends
from app.core.monitoring.metrics import MetricsCollector
from app.dependencies.services import get_metrics

# so here instead of defining @app.get("/health") in the main.py, we are defining @router.get("/health") in this file, and then we will include this router in the main API router in app/api/router.py
# then the main router will be included in the main FastAPI app in the main.py file, so that the clients can access the /health endpoint.
router = APIRouter(
    prefix="/health",
    tags=["Health"],
)
# sicne the prefix is /health => eventually the endpoints defined here are going to be accessible at /health/...
# the tag controls how the endpoints are grouped in the OpenAPI documentation, so that all the endpoints defined in this router are going to be grouped under the "Health" tag in the OpenAPI docs.


# this decorator below is used to register this endpoint with the router created above.
#
@router.get("")
async def health_check(
    # here we are injecting the MetricsCollector dependency
    metrics: MetricsCollector = Depends(get_metrics)
):
    return {
        "status": "healthy",
        "service": "production-rag-api",
        "metrics_initialized": metrics is not None,
    }
