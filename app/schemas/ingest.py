from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class IngestPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str | None = None
    slug: str | None = None
    force_rebuild: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> "IngestPostRequest":
        if not self.post_id and not self.slug:
            raise ValueError("post_id 和 slug 至少需要提供一个。")
        return self


class IngestRebuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    force: bool = False


class IngestJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    status: str
    target_slug: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
