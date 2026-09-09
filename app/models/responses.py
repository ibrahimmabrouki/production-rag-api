from pydantic import BaseModel, Field
from datetime import datetime


class ChatResponse(BaseModel):
    """Chat response returned to the client."""

    success: bool
    response: str | None = None

    cleaned_message: str | None = None

    input_security_notes: list[str] = []
    output_security_notes: list[str] = []

    cached: bool = False
    cache_type: str | None = None

    model_used: str | None = None
    error: str | None = None
    
    # processing_time: float
    # timestamp: datetime = Field(default_factory=lambda: datetime.now(
    #     datetime.timezone.utc), description="The timestamp when the response was generated.")


# this is just going to check the Health of the API and return a simple response
class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    environment: str
    version: str = "1.0.0"
    checks: dict = {}


class MetricsResponse(BaseModel):
    """Metrics endpoint response."""
    total_requests: int
    total_errors: int
    error_rate: float
    avg_latency_ms: float
    cache_hit_rate: float
    total_input_tokens: int
    total_output_tokens: int
