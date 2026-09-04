from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AdminCaseCreate(BaseModel):
    case_number: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    primary_investigator_id: str | None = None
    collaborator_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("collaborator_ids")
    @classmethod
    def dedupe_collaborators(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class AdminCaseAssignmentsUpdate(BaseModel):
    primary_investigator_id: str | None = None
    collaborator_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("collaborator_ids")
    @classmethod
    def dedupe_collaborators(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))
