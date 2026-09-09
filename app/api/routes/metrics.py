"""
This containes metrics-related endpoints

for example: GET /metrics
its purpose is to expose metrics about the API's performance and usage.

Application
    │
    ↓
MetricsCollector
    │
    ↓
Prometheus registry
    │
    ↓
GET /metrics
    │
    ↓
Prometheus scraper

"""


from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST


router = APIRouter()

@router.get("/metrics")
async def get_metrics() -> Response:
    """
    Expose the current Prometheus metrics registry.
    """

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

