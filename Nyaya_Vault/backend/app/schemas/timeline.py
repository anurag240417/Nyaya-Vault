from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TimelineStatementCreate(BaseModel):
    person_name: str = Field(min_length=1, max_length=300)
    location_name: str = Field(min_length=1, max_length=300)
    window_start: datetime
    window_end: datetime
    duration_minutes: int = Field(default=30, gt=0, le=24 * 60)
    document_version_id: str | None = None
    source_excerpt: str | None = Field(default=None, max_length=2000)

    @field_validator("window_end")
    @classmethod
    def _end_after_start(cls, value: datetime, info) -> datetime:
        start = info.data.get("window_start")
        if start is not None and value <= start:
            raise ValueError("window_end must be after window_start.")
        return value


class TravelTimeSet(BaseModel):
    location_a: str = Field(min_length=1, max_length=300)
    location_b: str = Field(min_length=1, max_length=300)
    minutes: int = Field(ge=0, le=7 * 24 * 60)