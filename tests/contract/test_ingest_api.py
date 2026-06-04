from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.api.deps import AppError
from app.api.routes.ingest import get_ingest_service


@dataclass
class FakeJob:
    """用于接口测试的简化任务对象。"""

    id: str
    job_type: str
    status: str
    target_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class StubIngestService:
    """为合同测试提供可控的同步服务替身。"""

    def sync_single_post(self, *, post_id: str | None, slug: str | None, force_rebuild: bool) -> FakeJob:
        assert post_id is None
        assert slug == "hello-nextjs"
        assert force_rebuild is False
        return FakeJob(
            id="job-single-001",
            job_type="single_post_sync",
            status="queued",
            target_slug=slug,
        )

    def rebuild_posts(self, *, scope: str, force: bool) -> FakeJob:
        assert scope == "all"
        assert force is False
        return FakeJob(
            id="job-rebuild-001",
            job_type="full_rebuild",
            status="queued",
        )

    def get_job(self, job_id: str) -> FakeJob:
        if job_id == "missing-job":
            raise AppError(
                error_code="not_found",
                message="找不到对应的同步任务。",
                status_code=404,
            )
        return FakeJob(
            id=job_id,
            job_type="single_post_sync",
            status="succeeded",
            target_slug="hello-nextjs",
            started_at=datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 6, 3, 10, 1, tzinfo=timezone.utc),
        )


def test_ingest_post_returns_accepted_job(client):
    """同步单篇文章接口应返回任务信息。"""
    client.app.dependency_overrides[get_ingest_service] = lambda: StubIngestService()
    try:
        response = client.post(
            "/api/v1/ingest/post",
            json={
                "slug": "hello-nextjs",
                "force_rebuild": False,
            },
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-single-001"
    assert payload["job_type"] == "single_post_sync"
    assert payload["status"] == "queued"
    assert payload["target_slug"] == "hello-nextjs"


def test_ingest_rebuild_returns_accepted_job(client):
    """全量重建接口应返回已受理任务。"""
    client.app.dependency_overrides[get_ingest_service] = lambda: StubIngestService()
    try:
        response = client.post(
            "/api/v1/ingest/rebuild",
            json={"scope": "all", "force": False},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-rebuild-001"
    assert payload["job_type"] == "full_rebuild"
    assert payload["status"] == "queued"


def test_ingest_job_query_returns_current_status(client):
    """任务查询接口应返回当前任务状态。"""
    client.app.dependency_overrides[get_ingest_service] = lambda: StubIngestService()
    try:
        response = client.get("/api/v1/ingest/jobs/job-single-001")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-single-001"
    assert payload["status"] == "succeeded"
    assert payload["started_at"].startswith("2026-06-03T10:00:00")
    assert payload["finished_at"].startswith("2026-06-03T10:01:00")


def test_ingest_job_query_returns_not_found_error(client):
    """查询不存在任务时应返回统一错误结构。"""
    client.app.dependency_overrides[get_ingest_service] = lambda: StubIngestService()
    try:
        response = client.get("/api/v1/ingest/jobs/missing-job")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "not_found"
    assert payload["message"] == "找不到对应的同步任务。"
