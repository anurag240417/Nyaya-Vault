
from pydantic import BaseModel, Field


class CertificateRequest(BaseModel):
    """
    Part A (device operator) is auto-filled from the logged-in officer and the
    document's own stored metadata - no input needed for that half.

    Part B (independent expert) cannot be auto-filled - the law requires an
    actual named expert to certify the hash/extraction process, so these
    fields are collected from the form each time a certificate is generated.
    """
    expert_name: str = Field(..., min_length=2, max_length=200)
    expert_designation: str = Field(..., min_length=2, max_length=200)
    expert_qualification: str = Field(..., min_length=2, max_length=300)
    place: str = Field(..., min_length=2, max_length=200)