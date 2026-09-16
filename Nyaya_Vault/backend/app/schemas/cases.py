from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.models import CaseStatus


class CaseCreate(BaseModel):
    case_number: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    status: CaseStatus | None = None


class CollaboratorChange(BaseModel):
    user_id: str