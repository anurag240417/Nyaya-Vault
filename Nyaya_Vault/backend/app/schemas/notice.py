from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.notice_types import NOTICE_TYPES

NoticeTypeKey = Literal[
    "STATUTORY_NOTICE", "BREACH_OF_CONTRACT", "EVICTION_NOTICE", "NOTICE_TO_PAY_RENT",
    "DEFAMATION_NOTICE", "CHEQUE_BOUNCE_NOTICE", "SPECIFIC_PERFORMANCE_NOTICE",
    "CONSUMER_PROTECTION_NOTICE", "SHOW_CAUSE_NOTICE", "DIVORCE_NOTICE",
    "RESTITUTION_OF_CONJUGAL_RIGHTS", "PARTITION_OF_PROPERTY", "COPYRIGHT_INFRINGEMENT",
    "TRADEMARK_INFRINGEMENT", "RECOVERY_OF_DUES", "NOTICE_TO_INSURANCE_COMPANY",
]


class LegalNoticeRequest(BaseModel):
    notice_type: NoticeTypeKey
    recipient_name: str = Field(..., min_length=2, max_length=200)
    recipient_address: str = Field(..., min_length=2, max_length=500)
    fields: dict[str, str] = Field(default_factory=dict)
    body: str = Field(..., min_length=10, max_length=10000)
    place: str = Field(..., min_length=2, max_length=200)

    @model_validator(mode="after")
    def _check_required_fields_for_type(self) -> "LegalNoticeRequest":
        spec = NOTICE_TYPES[self.notice_type]  # Literal already guarantees this key exists
        missing = [
            f.label for f in spec.fields
            if f.required and not (self.fields.get(f.key) or "").strip()
        ]
        if missing:
            raise ValueError(f"Missing required field(s) for {spec.title}: {', '.join(missing)}")
        return self