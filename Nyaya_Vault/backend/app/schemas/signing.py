from __future__ import annotations

from pydantic import BaseModel, Field


class SignatureVerifyRequest(BaseModel):
    public_key_pem: str = Field(..., min_length=1, max_length=4000)
    canonical_payload: str = Field(..., min_length=1, max_length=20000)
    signature_b64: str = Field(..., min_length=1, max_length=4000)
