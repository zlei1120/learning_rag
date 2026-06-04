from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.deps import AppError
from app.core.database import get_session_factory
from app.services.ingest_service import IngestService


def build_parser() -> argparse.ArgumentParser:
    """构造单篇同步脚本参数。"""
    parser = argparse.ArgumentParser(description="同步单篇博客文章到当前 RAG 存储。")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--post-id", dest="post_id", help="博客数据库中的文章主键。")
    target_group.add_argument("--slug", dest="slug", help="博客文章 slug。")
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="强制重建该文章对应的 RAG 索引。",
    )
    return parser


def serialize_job(job) -> dict[str, object]:
    """把任务对象转换为可打印 JSON。"""
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "target_slug": job.target_slug,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
    }


def main() -> int:
    """执行单篇同步。"""
    parser = build_parser()
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        service = IngestService(session)
        job = service.sync_single_post(
            post_id=args.post_id,
            slug=args.slug,
            force_rebuild=args.force_rebuild,
        )
        print(json.dumps(serialize_job(job), ensure_ascii=False, indent=2))
        return 0
    except AppError as exc:
        payload = {
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details or None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        payload = {
            "error_code": "internal_error",
            "message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
