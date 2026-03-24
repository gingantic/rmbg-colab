from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    error: str = Field(..., description="Human-readable error message")
