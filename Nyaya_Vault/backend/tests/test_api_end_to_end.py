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


def make_mp4() -> bytes:
    """Minimal bytes with a valid 'ftyp' box signature - enough to pass
    validate_file's magic-byte check. Not a real playable video; these
    tests only exercise upload/storage/versioning/processing-fallback,
    none of which require actually decodable video content."""
    return b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 32


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


def test_video_evidence_uploads_downloads_and_versions_like_any_document(client, gateway):
    case = create_case(client)
    video1 = make_mp4()
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "CCTV Footage - Main Gate", "document_type": "CCTV", "clearance_level": "RESTRICTED"},
        files={"file": ("cctv.mp4", video1, "video/mp4")},
    )
    assert up.status_code == 200, up.text
    doc_id, version_id = up.json()["documentId"], up.json()["versionId"]

    download = client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/download", headers=auth("admin-token"))
    assert download.status_code == 200
    assert download.content == video1
    assert download.headers["content-type"] == "video/mp4"

    video2 = make_mp4()
    v2 = client.post(
        f"/api/v1/documents/{doc_id}/versions", headers=auth("admin-token"),
        data={"change_summary": "Higher resolution re-export"},
        files={"file": ("cctv-v2.mp4", video2, "video/mp4")},
    )
    assert v2.status_code == 200, v2.text
    assert v2.json()["versionNumber"] == 2


def test_video_with_wrong_signature_is_rejected(client, gateway):
    case = create_case(client)
    fake = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Not actually a video", "document_type": "CCTV", "clearance_level": "RESTRICTED"},
        files={"file": ("fake.mp4", b"this is just plain text, not an mp4 container", "video/mp4")},
    )
    assert fake.status_code == 422
    assert "do not match" in fake.json()["detail"]


def test_video_processing_gracefully_finds_no_text_instead_of_crashing(client, gateway):
    """Video has no text to extract - processing must complete cleanly with
    zero entities, not crash trying to run PDF/image extraction on it."""
    case = create_case(client)
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Suspect Interview Recording", "document_type": "RECORDING", "clearance_level": "RESTRICTED"},
        files={"file": ("interview.mp4", make_mp4(), "video/mp4")},
    ).json()
    doc_id, version_id = up["documentId"], up["versionId"]

    processed = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["status"] == "READY"
    assert body["entities_created"] == 0
    assert body["ocr_used"] is False

    entities = client.get(f"/api/v1/document-versions/{version_id}/entities", headers=auth("admin-token")).json()
    assert entities == []



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


def test_second_fir_upload_is_blocked_in_favor_of_versioning(client, gateway):
    case = create_case(client)
    pdf1 = make_pdf("Original FIR narrative with enough text for native extraction to be used here.")
    first = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "FIR 214/2026", "document_type": "FIR", "clearance_level": "RESTRICTED"},
        files={"file": ("fir.pdf", pdf1, "application/pdf")},
    )
    assert first.status_code == 200, first.text
    fir_id = first.json()["documentId"]

    pdf2 = make_pdf("A second, unrelated FIR narrative that should not be allowed as a separate document.")
    second = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "FIR 214/2026 (corrected)", "document_type": "FIR", "clearance_level": "RESTRICTED"},
        files={"file": ("fir2.pdf", pdf2, "application/pdf")},
    )
    assert second.status_code == 409, second.text
    body = second.json()
    assert body["code"] == "CONFLICT"
    assert body["details"]["singleton_type"] == "FIR"
    assert body["details"]["existing_document_id"] == fir_id

    # The correct path: add it as a new version of the existing FIR instead.
    version = client.post(
        f"/api/v1/documents/{fir_id}/versions", headers=auth("admin-token"),
        data={"change_summary": "Corrected FIR narrative"},
        files={"file": ("fir-v2.pdf", pdf2, "application/pdf")},
    )
    assert version.status_code == 200, version.text
    assert version.json()["versionNumber"] == 2
    doc = client.get(f"/api/v1/documents/{fir_id}", headers=auth("admin-token")).json()
    assert doc["current_version_number"] == 2

    # Officers can still see the earlier version, not just the latest.
    versions = client.get(f"/api/v1/documents/{fir_id}/versions", headers=auth("admin-token")).json()
    assert [v["version_number"] for v in versions] == [2, 1]


def test_fir_singleton_check_is_punctuation_and_case_insensitive(client, gateway):
    case = create_case(client)
    pdf = make_pdf("FIR narrative text long enough for native extraction to succeed cleanly.")
    first = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "First Information Report", "document_type": "First Information Report", "clearance_level": "RESTRICTED"},
        files={"file": ("fir.pdf", pdf, "application/pdf")},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "FIR again", "document_type": "F.I.R.", "clearance_level": "RESTRICTED"},
        files={"file": ("fir2.pdf", pdf, "application/pdf")},
    )
    assert second.status_code == 409, second.text


def test_chargesheet_singleton_is_independent_of_fir(client, gateway):
    case = create_case(client)
    pdf = make_pdf("Some evidence narrative with enough text for native extraction to be used.")
    fir = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "FIR 88/2026", "document_type": "FIR", "clearance_level": "RESTRICTED"},
        files={"file": ("fir.pdf", pdf, "application/pdf")},
    )
    assert fir.status_code == 200, fir.text

    # A chargesheet is a different singleton type - having a primary FIR
    # must not block the first chargesheet.
    chargesheet = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Chargesheet 88/2026", "document_type": "Charge Sheet", "clearance_level": "RESTRICTED"},
        files={"file": ("cs.pdf", pdf, "application/pdf")},
    )
    assert chargesheet.status_code == 200, chargesheet.text

    second_chargesheet = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Chargesheet 88/2026 v2", "document_type": "CHARGESHEET", "clearance_level": "RESTRICTED"},
        files={"file": ("cs2.pdf", pdf, "application/pdf")},
    )
    assert second_chargesheet.status_code == 409, second_chargesheet.text


def test_singleton_type_is_scoped_per_case_not_global(client, gateway):
    case_a = create_case(client)
    case_b = create_case(client)
    pdf = make_pdf("FIR narrative text long enough for native extraction to succeed cleanly.")
    for case in (case_a, case_b):
        r = client.post(
            f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
            data={"title": "FIR", "document_type": "FIR", "clearance_level": "RESTRICTED"},
            files={"file": ("fir.pdf", pdf, "application/pdf")},
        )
        assert r.status_code == 200, r.text


def test_non_singleton_document_types_are_unaffected(client, gateway):
    case = create_case(client)
    pdf = make_pdf("Witness statement narrative with enough text for native extraction to be used.")
    for i in range(2):
        r = client.post(
            f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
            data={"title": f"Statement {i}", "document_type": "STATEMENT", "clearance_level": "RESTRICTED"},
            files={"file": (f"statement{i}.pdf", pdf, "application/pdf")},
        )
        assert r.status_code == 200, r.text


def test_department_gates_document_visibility_independent_of_clearance_and_case_access(client, gateway):
    """Department is a third access axis: same case, same clearance, but a
    document tagged for a different department must still be invisible - and
    the list endpoint must silently omit it rather than error."""
    case = create_case(client)
    forensic_officer = gateway.add_user(
        email="forensic@example.com", username="forensic_officer", role="INVESTIGATING_OFFICER",
        clearance="SECRET", department="FORENSICS", token="forensic-token",
    )
    prosecutor = gateway.add_user(
        email="pros2@example.com", username="prosecutor2", role="PROSECUTOR",
        clearance="SECRET", department="PROSECUTION", token="pros2-token",
    )
    for user in (forensic_officer, prosecutor):
        r = client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": user["id"]})
        assert r.status_code == 200, r.text

    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("forensic-token"),
        data={"title": "DNA analysis report", "clearance_level": "SECRET", "department": "FORENSICS"},
        files={"file": ("report.pdf", make_pdf("DNA match found"), "application/pdf")},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["documentId"]

    # Same case, same (higher) clearance, wrong department -> still denied.
    denied = client.get(f"/api/v1/documents/{doc_id}", headers=auth("pros2-token"))
    assert denied.status_code == 403

    listed = client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth("pros2-token"))
    assert listed.status_code == 200
    assert doc_id not in {d["id"] for d in listed.json()}

    # The owning department, and admin, can both still open it.
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth("forensic-token")).status_code == 200
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth("admin-token")).status_code == 200


def test_general_department_documents_stay_visible_to_everyone(client, gateway):
    """Backward compatibility: documents uploaded without picking a
    department (or explicitly GENERAL) must remain visible to any case
    member with sufficient clearance, same as before this feature existed."""
    case = create_case(client)
    io = profile(gateway, "io")
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": io["id"]})
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "General case notes", "clearance_level": "PUBLIC"},
        files={"file": ("notes.pdf", make_pdf("notes"), "application/pdf")},
    )
    assert up.status_code == 200, up.text
    assert client.get(f"/api/v1/documents/{up.json()['documentId']}", headers=auth("io-token")).status_code == 200


def test_uploader_cannot_tag_evidence_for_another_department(client, gateway):
    case = create_case(client)
    forensic_officer = gateway.add_user(
        email="forensic3@example.com", username="forensic_three", role="INVESTIGATING_OFFICER",
        clearance="SECRET", department="FORENSICS", token="forensic3-token",
    )
    client.post(f"/api/v1/cases/{case['id']}/collaborators", headers=auth("admin-token"), json={"user_id": forensic_officer["id"]})

    denied = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("forensic3-token"),
        data={"title": "Charge sheet", "clearance_level": "RESTRICTED", "department": "PROSECUTION"},
        files={"file": ("cs.pdf", make_pdf("charges"), "application/pdf")},
    )
    assert denied.status_code == 403

    # GENERAL is always allowed regardless of the uploader's own department.
    ok = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("forensic3-token"),
        data={"title": "Case notes", "clearance_level": "RESTRICTED", "department": "GENERAL"},
        files={"file": ("notes.pdf", make_pdf("notes"), "application/pdf")},
    )
    assert ok.status_code == 200, ok.text


def test_admin_can_set_a_users_department_but_a_user_cannot_self_assign(client, gateway):
    clerk = profile(gateway, "clerk")
    r = client.patch(
        f"/api/v1/users/{clerk['id']}", headers=auth("admin-token"),
        json={"role": "CLERK", "clearance_level": "PUBLIC", "department": "POLICE", "is_active": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["department"] == "POLICE"

    denied = client.patch(
        f"/api/v1/users/{clerk['id']}", headers=auth("clerk-token"),
        json={"role": "CLERK", "clearance_level": "PUBLIC", "department": "JUDICIARY", "is_active": True},
    )
    assert denied.status_code == 403


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