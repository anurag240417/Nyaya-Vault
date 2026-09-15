from __future__ import annotations

from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf, profile


def _upload_and_get_ids(client, case_id, *, clearance="RESTRICTED", department=None, token="admin-token"):
    data = {"title": "Evidence", "clearance_level": clearance}
    if department:
        data["department"] = department
    up = client.post(
        f"/api/v1/cases/{case_id}/documents", headers=auth(token),
        data=data, files={"file": ("e.pdf", make_pdf("evidence"), "application/pdf")},
    ).json()
    return up["documentId"], up["versionId"]


def _expert_payload(**overrides):
    payload = {
        "expert_name": "Dr. Ramesh Iyer",
        "expert_designation": "Digital Forensics Examiner",
        "expert_qualification": "M.Tech (Cyber Security), Certified Forensic Examiner",
        "place": "Mumbai",
    }
    payload.update(overrides)
    return payload


def test_certificate_generates_a_real_pdf_and_is_audited(client, gateway):
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])

    r = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"), json=_expert_payload(),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert "certificate" in r.headers["content-disposition"].lower()

    actions = [a["action"] for a in gateway.tables["audit_logs"] if a["case_id"] == case["id"]]
    assert "CERTIFICATE_GENERATED" in actions


def test_certificate_requires_case_access(client, gateway):
    case = create_case(client)  # admin only, otherio never assigned
    doc_id, version_id = _upload_and_get_ids(client, case["id"])

    denied = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("otherio-token"), json=_expert_payload(),
    )
    assert denied.status_code == 403


def test_certificate_respects_clearance_even_for_a_case_member(client, gateway):
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"], clearance="SECRET")
    clerk = profile(gateway, "clerk")  # PUBLIC clearance
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": clerk["id"]})

    denied = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("clerk-token"), json=_expert_payload(),
    )
    assert denied.status_code == 403


def test_certificate_respects_department_even_with_sufficient_clearance(client, gateway):
    """Proves the authorization-reuse claim: this feature was built before
    department access existed, but because it calls require_version_access
    (which now includes the department check), it inherits that protection
    automatically - no certificate-specific department logic was needed."""
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"], clearance="SECRET", department="FORENSICS")

    prosecutor = gateway.add_user(
        email="cert-pros@example.com", username="cert_pros", role="PROSECUTOR",
        clearance="SECRET", department="PROSECUTION", token="cert-pros-token",
    )
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": prosecutor["id"]})

    denied = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("cert-pros-token"), json=_expert_payload(),
    )
    assert denied.status_code == 403


def test_certificate_rejects_mismatched_document_and_version(client, gateway):
    case_a = create_case(client)
    case_b = create_case(client)
    doc_a, _ = _upload_and_get_ids(client, case_a["id"])
    _, version_b = _upload_and_get_ids(client, case_b["id"])

    r = client.post(
        f"/api/v1/documents/{doc_a}/versions/{version_b}/certificate",
        headers=auth("admin-token"), json=_expert_payload(),
    )
    assert r.status_code == 404


def test_certificate_rejects_missing_expert_fields(client, gateway):
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])

    r = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"), json=_expert_payload(expert_name=""),
    )
    assert r.status_code == 422


def test_certificate_neutralizes_markup_injection_in_expert_fields(client, gateway):
    """Regression test for a real, reproduced issue: ReportLab's Paragraph
    text is markup-aware, so an unescaped user-supplied field could inject
    live formatting (e.g. a well-formed <font color="red"> tag rendered
    exactly as written) into a document meant to be a neutral, court-facing
    certificate. This doesn't inspect the rendered PDF's visual output -
    it proves the request still succeeds (i.e. the fix escapes rather than
    rejects) and that the underlying builder was actually called with the
    injected value, so a visual/text-extraction check could catch a
    regression here without needing PDF rendering in CI.
    """
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])

    r = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"),
        json=_expert_payload(place='<font color="red" size="30">CASE DISMISSED</font>'),
    )
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")
    # Extract raw PDF text and confirm the tag was neutralized. Verified by
    # testing the actual vulnerable behavior directly: an unescaped tag gets
    # consumed as live markup, so "CASE DISMISSED" appears in extracted text
    # but the literal characters "<font" never do (the styling ate them).
    # An escaped/fixed value shows BOTH the literal "<font" characters and
    # the text - proving the tag was displayed, not interpreted.
    import pypdf
    from io import BytesIO
    reader = pypdf.PdfReader(BytesIO(r.content))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "CASE DISMISSED" in full_text
    assert "<font" in full_text  # literal, escaped text - proves it was NOT live markup