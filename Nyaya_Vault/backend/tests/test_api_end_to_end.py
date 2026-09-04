from __future__ import annotations

import io

import fitz

from tests.conftest import auth


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 760), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def profile(gateway, username): return next(r for r in gateway.tables["profiles"] if r["username"] == username)


def create_case(client, token="admin-token"):
    response = client.post("/api/v1/cases", headers=auth(token), json={"case_number": "FIR-2026-001", "title": "Demo Investigation", "description": "Secure case"})
    assert response.status_code == 201, response.text
    return response.json()


def test_auth_and_health(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/auth/me").status_code == 401
    me = client.get("/api/v1/auth/me", headers=auth("admin-token"))
    assert me.status_code == 200
    assert me.json()["role"] == "ADMIN"


def test_case_collaborator_authorization_and_denied_audit(client, gateway):
    case = create_case(client)
    io = profile(gateway, "io"); other = profile(gateway, "otherio"); clerk = profile(gateway, "clerk")

    # Admin assigns IO.
    r = client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": io["id"]})
    assert r.status_code == 200

    # Assigned IO may manage collaborators.
    r = client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("io-token"), json={"user_id": clerk["id"]})
    assert r.status_code == 200

    # Unassigned IO must be denied even though the role itself is correct.
    r = client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("otherio-token"), json={"user_id": other["id"]})
    assert r.status_code == 403
    assert any(a["action"] == "ACCESS_DENIED" and a["result"] == "DENIED" for a in gateway.tables["audit_logs"])

    collabs = client.get(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("io-token"))
    assert collabs.status_code == 200
    assert {c["username"] for c in collabs.json()} >= {"admin", "io", "clerk"}


def test_document_clearance_is_separate_from_case_access(client, gateway):
    case = create_case(client)
    clerk = profile(gateway, "clerk")
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": clerk["id"]})
    pdf = make_pdf("Secret evidence content that is long enough to be a native text PDF for extraction testing. " * 2)
    uploaded = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Secret Report", "document_type": "REPORT", "clearance_level": "SECRET"},
        files={"file": ("secret.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()["documentId"]
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth("clerk-token")).status_code == 403
    assert client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth("clerk-token")).json() == []


def test_document_upload_version_download_and_search(client, gateway):
    case = create_case(client)
    pdf1 = make_pdf("Evidence alpha. FIR No 214/2026. Contact 9876543210. This paragraph has enough text for native extraction and search indexing.")
    r = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Witness Statement", "document_type": "STATEMENT", "clearance_level": "RESTRICTED"},
        files={"file": ("statement.pdf", pdf1, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    payload = r.json(); doc_id = payload["documentId"]; version_id = payload["versionId"]

    download = client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/download", headers=auth("admin-token"))
    assert download.status_code == 200 and download.content == pdf1

    pdf2 = make_pdf("Version two evidence with corrected details and additional narrative. " * 2)
    v2 = client.post(
        f"/api/v1/documents/{doc_id}/versions", headers=auth("admin-token"), data={"change_summary": "Correction"},
        files={"file": ("statement-v2.pdf", pdf2, "application/pdf")},
    )
    assert v2.status_code == 200, v2.text
    assert v2.json()["versionNumber"] == 2
    versions = client.get(f"/api/v1/documents/{doc_id}/versions", headers=auth("admin-token")).json()
    assert [v["version_number"] for v in versions] == [2, 1]


def test_processing_entity_review_redaction_and_true_redacted_export(client, gateway):
    case = create_case(client)
    phone = "9876543210"
    text = f"Witness Ravi Sharma provided a statement. Contact phone {phone}. This document contains enough additional narrative to ensure native PDF text extraction is used instead of OCR."
    pdf = make_pdf(text)
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "PII Evidence", "document_type": "STATEMENT", "clearance_level": "RESTRICTED"},
        files={"file": ("pii.pdf", pdf, "application/pdf")},
    ).json()
    doc_id, version_id = up["documentId"], up["versionId"]

    processed = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "READY"
    entities = client.get(f"/api/v1/document-versions/{version_id}/entities", headers=auth("admin-token")).json()
    phone_entity = next(e for e in entities if e["entity_type"] == "PHONE" and e["value"] == phone)

    review = client.post(f"/api/v1/documents/{doc_id}/entities/review", headers=auth("admin-token"), json={"confirmed_ids": [phone_entity["id"]], "rejected_ids": []})
    assert review.status_code == 200

    # Re-processing preserves confirmed entity and generates redaction suggestions from it.
    processed2 = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert processed2.status_code == 200, processed2.text
    redactions = client.get(f"/api/v1/document-versions/{version_id}/redactions", headers=auth("admin-token")).json()
    phone_redaction = next(r for r in redactions if r["entity_type"] == "PHONE")

    approved = client.post(f"/api/v1/documents/{doc_id}/redactions/review", headers=auth("admin-token"), json={"approved_ids": [phone_redaction["id"]], "rejected_ids": []})
    assert approved.status_code == 200
    export = client.post(f"/api/v1/documents/{doc_id}/redacted-export", headers=auth("admin-token"))
    assert export.status_code == 200, export.text
    redacted_pdf = fitz.open(stream=export.content, filetype="pdf")
    extracted = "".join(page.get_text() for page in redacted_pdf)
    redacted_pdf.close()
    assert phone not in extracted
    assert any(a["action"] == "REPORT_EXPORTED" for a in gateway.tables["audit_logs"])


def test_admin_management_audit_and_integrity(client, gateway):
    case = create_case(client)
    clerk = profile(gateway, "clerk")
    users = client.get("/api/v1/users", headers=auth("admin-token"))
    assert users.status_code == 200 and len(users.json()) >= 4
    update = client.patch(f"/api/v1/users/{clerk['id']}", headers=auth("admin-token"), json={"role": "PROSECUTOR", "clearance_level": "CONFIDENTIAL", "is_active": True})
    assert update.status_code == 200
    assert update.json()["role"] == "PROSECUTOR"

    audit = client.get(f"/api/v1/cases/{case['id']}/audit", headers=auth("admin-token"))
    assert audit.status_code == 200 and audit.json()
    integrity = client.get("/api/v1/integrity/verify", headers=auth("admin-token"))
    assert integrity.status_code == 200 and integrity.json()["valid"] is True


def test_role_gates_admin_does_not_bypass_clearance_and_inactive_is_blocked(client, gateway):
    assert client.post("/api/v1/cases", headers=auth("clerk-token"), json={"case_number":"X-1","title":"Denied case","description":"x"}).status_code == 403
    assert client.get("/api/v1/auth/me", headers=auth("inactive-token")).status_code == 403

    case = create_case(client)
    pdf = make_pdf("Top secret evidence content with enough native text to satisfy extraction heuristics. " * 2)
    uploaded = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title":"Secret","document_type":"REPORT","clearance_level":"SECRET"},
        files={"file": ("secret.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200
    doc_id = uploaded.json()["documentId"]
    # ADMIN can see the case globally but still cannot read evidence above their clearance.
    assert client.get(f"/api/v1/cases/{case['id']}", headers=auth("lowadmin-token")).status_code == 200
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth("lowadmin-token")).status_code == 403


def test_collaborator_candidates_are_case_scoped_and_mime_spoofing_is_rejected(client, gateway):
    case = create_case(client)
    io = profile(gateway, "io")
    # Unassigned IO cannot even enumerate candidates for an unrelated case.
    assert client.get(f"/api/v1/cases/{case['id']}/collaborator-candidates", headers=auth("io-token")).status_code == 403
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": io["id"]})
    candidates = client.get(f"/api/v1/cases/{case['id']}/collaborator-candidates", headers=auth("io-token"))
    assert candidates.status_code == 200

    fake_pdf = b"this is not actually a PDF"
    upload = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title":"Spoof","document_type":"REPORT","clearance_level":"PUBLIC"},
        files={"file": ("spoof.pdf", fake_pdf, "application/pdf")},
    )
    assert upload.status_code == 422


def test_backend_search_respects_assignment_and_clearance(client, gateway):
    case = create_case(client)
    clerk = profile(gateway, "clerk")
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": clerk["id"]})
    public_pdf = make_pdf("The unique searchable keyword is heliograph and this sentence is long enough for native extraction. " * 2)
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title":"Public Evidence","document_type":"REPORT","clearance_level":"PUBLIC"},
        files={"file": ("public.pdf", public_pdf, "application/pdf")},
    ).json()
    client.post(f"/api/v1/documents/{up['documentId']}/process", headers=auth("admin-token"), json={"version_id":up["versionId"]})
    result = client.get("/api/v1/search?q=heliograph", headers=auth("clerk-token"))
    assert result.status_code == 200
    assert any(r["document_id"] == up["documentId"] for r in result.json())
    # Unassigned IO has no case scope and receives no result.
    assert client.get("/api/v1/search?q=heliograph", headers=auth("otherio-token")).json() == []


def test_admin_case_management_create_primary_multi_assign_and_reassign(client, gateway):
    io = profile(gateway, "io")
    other_io = profile(gateway, "otherio")
    clerk = profile(gateway, "clerk")

    created = client.post(
        "/api/v1/admin/cases",
        headers=auth("admin-token"),
        json={
            "case_number": "ADM-2026-100",
            "title": "Admin managed investigation",
            "description": "Created and assigned from Administration.",
            "primary_investigator_id": io["id"],
            "collaborator_ids": [clerk["id"]],
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["primary_investigator"]["id"] == io["id"]
    assert {c["user_id"] for c in payload["collaborators"]} >= {io["id"], clerk["id"]}

    # Assignment visibility contract: every newly assigned non-admin must see the
    # case through the normal case-list API immediately after the admin write.
    clerk_cases = client.get("/api/v1/cases", headers=auth("clerk-token"))
    io_cases = client.get("/api/v1/cases", headers=auth("io-token"))
    assert clerk_cases.status_code == 200, clerk_cases.text
    assert io_cases.status_code == 200, io_cases.text
    assert payload["id"] in {row["id"] for row in clerk_cases.json()}
    assert payload["id"] in {row["id"] for row in io_cases.json()}

    listed = client.get("/api/v1/admin/cases", headers=auth("admin-token"))
    assert listed.status_code == 200
    assert any(c["id"] == payload["id"] for c in listed.json())

    reassigned = client.patch(
        f"/api/v1/admin/cases/{payload['id']}/assignments",
        headers=auth("admin-token"),
        json={
            "primary_investigator_id": other_io["id"],
            "collaborator_ids": [other_io["id"]],
        },
    )
    assert reassigned.status_code == 200, reassigned.text
    row = reassigned.json()
    assert row["primary_investigator"]["id"] == other_io["id"]
    assigned_ids = {c["user_id"] for c in row["collaborators"]}
    assert other_io["id"] in assigned_ids
    assert clerk["id"] not in assigned_ids
    assert io["id"] not in assigned_ids

    # Reassignment must be reflected in normal case visibility as well.
    assert payload["id"] not in {row["id"] for row in client.get("/api/v1/cases", headers=auth("clerk-token")).json()}
    assert payload["id"] not in {row["id"] for row in client.get("/api/v1/cases", headers=auth("io-token")).json()}
    assert payload["id"] in {row["id"] for row in client.get("/api/v1/cases", headers=auth("otherio-token")).json()}
    assert any(a["action"] == "CASE_UNASSIGNED" and a["metadata"].get("unassigned_user_id") == clerk["id"] for a in gateway.tables["audit_logs"])


def test_primary_investigator_visible_despite_assignment_row_drift(client, gateway):
    """Guards against 'assigned but can't see the case': if cases.primary_investigator_id
    is set but the case_assignments row is missing (partial migration, hand-edited row,
    a mid-transaction failure), the recorded primary investigator must still see and
    open the case rather than being silently locked out."""
    case = create_case(client)
    io = profile(gateway, "io")

    # Simulate drift directly: record the assignment on the case row only,
    # without inserting into case_assignments (what require_case_access /
    # accessible_case_ids used to rely on exclusively).
    for row in gateway.tables["cases"]:
        if row["id"] == case["id"]:
            row["primary_investigator_id"] = io["id"]
    assert not any(
        a["case_id"] == case["id"] and a["user_id"] == io["id"]
        for a in gateway.tables["case_assignments"]
    )

    listed = client.get("/api/v1/cases", headers=auth("io-token"))
    assert listed.status_code == 200
    assert case["id"] in {row["id"] for row in listed.json()}

    fetched = client.get(f"/api/v1/cases/{case['id']}", headers=auth("io-token"))
    assert fetched.status_code == 200


def test_admin_case_management_is_admin_only(client, gateway):
    io = profile(gateway, "io")
    denied = client.post(
        "/api/v1/admin/cases",
        headers=auth("io-token"),
        json={
            "case_number": "ADM-DENIED-1",
            "title": "Must not be created",
            "description": None,
            "primary_investigator_id": io["id"],
            "collaborator_ids": [],
        },
    )
    assert denied.status_code == 403
    assert client.get("/api/v1/admin/cases", headers=auth("io-token")).status_code == 403