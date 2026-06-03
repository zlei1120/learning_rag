from __future__ import annotations

from fastapi import APIRouter

from app.schemas.ingest import IngestJobResponse, IngestPostRequest, IngestRebuildRequest

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("/post", response_model=IngestJobResponse, status_code=202)
async def post_ingest_single(request: IngestPostRequest) -> IngestJobResponse:
    return IngestJobResponse(
        job_id="placeholder-job",
        job_type="single_post_sync",
        status="queued",
        target_slug=request.slug,
    )


@router.post("/rebuild", response_model=IngestJobResponse, status_code=202)
async def post_ingest_rebuild(_: IngestRebuildRequest) -> IngestJobResponse:
    return IngestJobResponse(
        job_id="placeholder-rebuild-job",
        job_type="full_rebuild",
        status="queued",
    )


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(job_id: str) -> IngestJobResponse:
    return IngestJobResponse(
        job_id=job_id,
        job_type="single_post_sync",
        status="queued",
    )
