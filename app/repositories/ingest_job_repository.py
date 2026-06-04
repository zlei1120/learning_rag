from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingest_job import IngestJob


class IngestJobRepository:
    """管理同步任务状态。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_type: str,
        target_post_id: str | None = None,
        target_slug: str | None = None,
        trigger_source: str = "api",
        payload_json: dict[str, object] | None = None,
    ) -> IngestJob:
        """创建任务记录。"""
        job = IngestJob(
            job_type=job_type,
            target_post_id=target_post_id,
            target_slug=target_slug,
            trigger_source=trigger_source,
            payload_json=payload_json,
            status="queued",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_id(self, job_id: str) -> IngestJob | None:
        """按任务主键读取任务。"""
        statement = select(IngestJob).where(IngestJob.id == job_id)
        return self.session.execute(statement).scalar_one_or_none()

    def mark_running(self, job: IngestJob) -> IngestJob:
        """标记任务开始执行。"""
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        self.session.flush()
        return job

    def mark_succeeded(self, job: IngestJob) -> IngestJob:
        """标记任务执行成功。"""
        job.status = "succeeded"
        if job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = None
        self.session.flush()
        return job

    def mark_failed(self, job: IngestJob, error_message: str) -> IngestJob:
        """标记任务执行失败。"""
        job.status = "failed"
        if job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error_message
        self.session.flush()
        return job
