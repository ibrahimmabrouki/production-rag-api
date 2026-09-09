from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: str | None = None
    request_id: str | None = None