"""GET /health — liveness + readiness probe for K8s and load balancers."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")