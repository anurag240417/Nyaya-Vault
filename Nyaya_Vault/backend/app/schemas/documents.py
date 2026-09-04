from __future__ import annotations

from pydantic import BaseModel, Field


class EntityReview(BaseModel):
    confirmed_ids: list[str] = Field(default_factory=list)
    rejected_ids: list[str] = Field(default_factory=list)


class RedactionReview(BaseModel):
    approved_ids: list[str] = Field(default_factory=list)
    rejected_ids: list[str] = Field(default_factory=list)


class ProcessRequest(BaseModel):
    version_id: str
