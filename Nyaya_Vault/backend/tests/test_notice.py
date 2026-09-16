from __future__ import annotations

from io import BytesIO

import pypdf
import pytest

from app.services.notice_types import NOTICE_TYPES
from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf


def _minimal_fields(notice_type: str) -> dict[str, str]:
    spec = NOTICE_TYPES[notice_type]
    return {f.key: f"Sample {f.label}" for f in spec.fields if f.required}


def _notice_payload(notice_type: str, **overrides) -> dict:
    payload = {
        "notice_type": notice_type,
        "recipient_name": "Ramesh Kumar",
        "recipient_address": "123 MG Road, Pune, Maharashtra",
        "fields": _minimal_fields(notice_type),
        "body": "This is the substantive body of the notice, provided by the issuing officer.",
        "place": "Pune",
    }
    payload.update(overrides)
    return payload


def test_get_notice_types_returns_all_sixteen_registered_types(client):
    case = create_case(client)
    r = client.get(f"/api/v1/cases/{case['id']}/notices/types", headers=auth("admin-token"))
    assert r.status_code == 200, r.text
    keys = {t["key"] for t in r.json()}
    assert keys == set(NOTICE_TYPES.keys())
    assert len(keys) == 16


@pytest.mark.parametrize("notice_type", list(NOTICE_TYPES.keys()))
def test_every_registered_notice_type_generates_a_real_pdf(client, notice_type):
    case = create_case(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"),
        json=_notice_payload(notice_type),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")

    # Confirm the notice's own title text actually made it into the PDF -
    # not just that some valid PDF came back.
    reader = pypdf.PdfReader(BytesIO(r.content))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert NOTICE_TYPES[notice_type].title.upper() in full_text.upper()
    if NOTICE_TYPES[notice_type].statute_reference:
        assert NOTICE_TYPES[notice_type].statute_reference in full_text


def test_notice_requires_case_access(client):
    case = create_case(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/notices", headers=auth("otherio-token"),
        json=_notice_payload("SHOW_CAUSE_NOTICE"),
    )
    assert r.status_code == 403


def test_notice_rejects_missing_required_type_specific_field(client):
    case = create_case(client)
    payload = _notice_payload("CHEQUE_BOUNCE_NOTICE")
    del payload["fields"]["cheque_number"]  # a required field for this type
    r = client.post(f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"), json=payload)
    assert r.status_code == 422
    assert "cheque_number" in r.text.lower() or "Cheque number" in r.text


def test_notice_rejects_unknown_notice_type(client):
    case = create_case(client)
    payload = _notice_payload("STATUTORY_NOTICE")
    payload["notice_type"] = "MADE_UP_NOTICE_TYPE"
    r = client.post(f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"), json=payload)
    assert r.status_code == 422


def test_notice_generation_is_audited(client, gateway):
    case = create_case(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"),
        json=_notice_payload("DEFAMATION_NOTICE"),
    )
    assert r.status_code == 200, r.text
    actions = [a["action"] for a in gateway.tables["audit_logs"] if a["case_id"] == case["id"]]
    assert "LEGAL_NOTICE_GENERATED" in actions


def test_notice_neutralizes_markup_injection_in_body_and_fields(client):
    """Same regression class as the certificate's injection fix - free-text
    fields (body, recipient details, structured fields) must not let a
    well-formed tag render as live formatting in a document meant to be
    read at face value."""
    case = create_case(client)
    payload = _notice_payload(
        "SHOW_CAUSE_NOTICE",
        body='<font color="red" size="30">CASE DISMISSED</font>',
    )
    r = client.post(f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"), json=payload)
    assert r.status_code == 200, r.text
    reader = pypdf.PdfReader(BytesIO(r.content))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "CASE DISMISSED" in full_text
    assert "<font" in full_text  # literal, escaped text - proves it was NOT live markup


def test_signature_stamp_present_with_issuer_details_not_double_escaped(client):
    """The issuer signature stamp must show the real username/role - and
    specifically must not be double-escaped (a bug I introduced and caught
    myself while wiring the certificate's stamp: passing an already-escaped
    value into a function that escapes again turns '&' into '&amp;amp;')."""
    case = create_case(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"),
        json=_notice_payload("STATUTORY_NOTICE"),
    )
    assert r.status_code == 200, r.text
    reader = pypdf.PdfReader(BytesIO(r.content))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Digitally Signed by" in full_text
    assert "admin" in full_text  # the actual username, not a placeholder
    assert "&amp;" not in full_text  # would indicate double-escaping if present


def test_certificate_stamp_also_not_double_escaped_after_department_wiring(client, gateway):
    """Regression test for the same double-escape bug, on the certificate
    side specifically - device_operator_name is used both in the Part A
    paragraph (needs escaping) and the signature stamp (escapes internally);
    passing the already-escaped value to the stamp would double-escape it."""
    case = create_case(client)
    pdf = make_pdf("evidence")
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Evidence", "clearance_level": "PUBLIC"},
        files={"file": ("e.pdf", pdf, "application/pdf")},
    ).json()
    r = client.post(
        f"/api/v1/documents/{up['documentId']}/versions/{up['versionId']}/certificate",
        headers=auth("admin-token"),
        json={
            "expert_name": "Dr. Test", "expert_designation": "Examiner",
            "expert_qualification": "M.Tech", "place": "Mumbai",
        },
    )
    assert r.status_code == 200, r.text
    reader = pypdf.PdfReader(BytesIO(r.content))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Digitally Signed by" in full_text
    assert "&amp;" not in full_text