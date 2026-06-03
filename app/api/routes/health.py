from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database_health
from app.schemas.common import HealthResponse
from app.services.orchestration_service import get_orchestration_runtime

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    settings = get_settings()
    database_status = check_database_health()
    graph_runtime = get_orchestration_runtime().to_health_label()
    service_status = "ok" if database_status == "ok" else "degraded"

    return HealthResponse(
        status=service_status,
        service=settings.app_name,
        version=settings.app_version,
        database=database_status,
        graph_runtime=graph_runtime,
    )
