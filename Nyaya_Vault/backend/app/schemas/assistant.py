from __future__ import annotations

from pydantic import BaseModel, Field


class AskQuestion(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)