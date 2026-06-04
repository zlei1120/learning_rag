from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.ingest import IngestJobResponse, IngestPostRequest, IngestRebuildRequest
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


def get_ingest_service(session: Session = Depends(get_db_session)) -> IngestService:
    """为同步接口提供服务实例。"""
    return IngestService(session)


def build_ingest_job_response(job) -> IngestJobResponse:
    """把任务 ORM 对象转换成接口响应。"""
    return IngestJobResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        target_slug=job.target_slug,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
    )


@router.post("/post", response_model=IngestJobResponse, status_code=202)
def post_ingest_single(
    request: IngestPostRequest,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestJobResponse:
    job = ingest_service.sync_single_post(
        post_id=request.post_id,
        slug=request.slug,
        force_rebuild=request.force_rebuild,
    )
    return build_ingest_job_response(job)


@router.post("/rebuild", response_model=IngestJobResponse, status_code=202)
def post_ingest_rebuild(
    request: IngestRebuildRequest,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestJobResponse:
    job = ingest_service.rebuild_posts(scope=request.scope, force=request.force)
    return build_ingest_job_response(job)


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
def get_ingest_job(
    job_id: str,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestJobResponse:
    job = ingest_service.get_job(job_id)
    return build_ingest_job_response(job)
