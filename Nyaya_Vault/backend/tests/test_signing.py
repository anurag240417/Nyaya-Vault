from __future__ import annotations

import base64
import json
from io import BytesIO

import pypdf

from app.services.signing import canonical_json, verify_signature
from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf
from tests.test_certificate import _expert_payload, _upload_and_get_ids


def _pdf_text_no_whitespace(content: bytes) -> str:
    reader = pypdf.PdfReader(BytesIO(content))
    return "".join("".join(page.extract_text().split()) for page in reader.pages)


def _capture_signatures(client):
    """Wraps SigningService.sign_for_user so a test can verify the exact
    block that was embedded in the PDF without parsing it back out."""
    signing = client.app.state.casevault.signing
    captured: list[dict] = []
    original = signing.sign_for_user

    async def recording(user, *, purpose, payload):
        block = await original(user, purpose=purpose, payload=payload)
        captured.append(block)
        return block

    signing.sign_for_user = recording
    return captured


def test_my_signing_key_is_issued_once_and_never_exposes_the_private_key(client, gateway):
    first = client.get("/api/v1/auth/signing-key", headers=auth("admin-token"))
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")
    assert "private" not in json.dumps(body).lower()

    second = client.get("/api/v1/auth/signing-key", headers=auth("admin-token")).json()
    assert second["public_key_pem"] == body["public_key_pem"]
    assert len(gateway.tables["user_signing_keys"]) == 1
    assert [a["action"] for a in gateway.tables["audit_logs"]].count("SIGNING_KEY_GENERATED") == 1


def test_stored_private_key_is_encrypted_not_plaintext(client, gateway):
    client.get("/api/v1/auth/signing-key", headers=auth("admin-token"))
    stored = gateway.tables["user_signing_keys"][0]["private_key_encrypted"]
    assert "PRIVATE KEY" not in stored


def test_each_user_gets_a_different_key(client, gateway):
    a = client.get("/api/v1/auth/signing-key", headers=auth("admin-token")).json()
    b = client.get("/api/v1/auth/signing-key", headers=auth("io-token")).json()
    assert a["public_key_pem"] != b["public_key_pem"]


def test_certificate_is_really_signed_and_signature_verifies(client, gateway):
    captured = _capture_signatures(client)
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])

    r = client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"), json=_expert_payload(),
    )
    assert r.status_code == 200, r.text
    block = captured[-1]

    assert verify_signature(
        public_key_pem=block["public_key_pem"], canonical_payload=block["canonical_payload"],
        signature_b64=block["signature_b64"],
    )
    signed = json.loads(block["canonical_payload"])
    assert signed["purpose"] == "SECTION_63_CERTIFICATE"
    assert signed["document_id"] == doc_id and signed["version_id"] == version_id
    assert signed["sha256"] == next(v for v in gateway.tables["document_versions"] if v["id"] == version_id)["sha256"]

    text = _pdf_text_no_whitespace(r.content)
    assert block["signature_b64"] in text
    assert block["fingerprint"] in text
    assert "NOTacryptographic" not in text  # the old "not a signature" disclaimer must be gone

    meta = [a for a in gateway.tables["audit_logs"] if a["action"] == "CERTIFICATE_GENERATED"][-1]["metadata"]
    assert meta["signature_fingerprint"] == block["fingerprint"]


def test_tampering_with_any_signed_field_breaks_verification(client, gateway):
    captured = _capture_signatures(client)
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])
    client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"), json=_expert_payload(),
    )
    block = captured[-1]

    forged = json.loads(block["canonical_payload"])
    forged["sha256"] = "0" * 64
    assert not verify_signature(
        public_key_pem=block["public_key_pem"], canonical_payload=canonical_json(forged),
        signature_b64=block["signature_b64"],
    )

    other_key = client.get("/api/v1/auth/signing-key", headers=auth("io-token")).json()["public_key_pem"]
    assert not verify_signature(
        public_key_pem=other_key, canonical_payload=block["canonical_payload"],
        signature_b64=block["signature_b64"],
    )


def test_legal_notice_is_signed_too(client, gateway):
    captured = _capture_signatures(client)
    case = create_case(client)
    r = client.post(
        f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"),
        json={
            "notice_type": "SHOW_CAUSE_NOTICE", "recipient_name": "R. Sharma",
            "recipient_address": "12 MG Road, Pune", "fields": {},
            "body": "You are called upon to show cause within seven days.", "place": "Pune",
        },
    )
    if r.status_code == 422:  # required per-type fields vary; reuse whatever the type demands
        from app.services.notice_types import NOTICE_TYPES
        fields = {f.key: "x" for f in NOTICE_TYPES["SHOW_CAUSE_NOTICE"].fields}
        r = client.post(
            f"/api/v1/cases/{case['id']}/notices", headers=auth("admin-token"),
            json={
                "notice_type": "SHOW_CAUSE_NOTICE", "recipient_name": "R. Sharma",
                "recipient_address": "12 MG Road, Pune", "fields": fields,
                "body": "You are called upon to show cause within seven days.", "place": "Pune",
            },
        )
    assert r.status_code == 200, r.text
    block = captured[-1]
    assert json.loads(block["canonical_payload"])["purpose"] == "LEGAL_NOTICE"
    assert verify_signature(
        public_key_pem=block["public_key_pem"], canonical_payload=block["canonical_payload"],
        signature_b64=block["signature_b64"],
    )
    assert block["signature_b64"] in _pdf_text_no_whitespace(r.content)


def test_verify_endpoint_accepts_good_and_rejects_bad_signatures(client, gateway):
    captured = _capture_signatures(client)
    case = create_case(client)
    doc_id, version_id = _upload_and_get_ids(client, case["id"])
    client.post(
        f"/api/v1/documents/{doc_id}/versions/{version_id}/certificate",
        headers=auth("admin-token"), json=_expert_payload(),
    )
    block = captured[-1]
    body = {
        "public_key_pem": block["public_key_pem"], "canonical_payload": block["canonical_payload"],
        "signature_b64": block["signature_b64"],
    }
    assert client.post("/api/v1/signatures/verify", headers=auth("clerk-token"), json=body).json() == {"valid": True}

    body["canonical_payload"] = body["canonical_payload"].replace("SECTION_63", "SECTION_64")
    assert client.post("/api/v1/signatures/verify", headers=auth("clerk-token"), json=body).json() == {"valid": False}

    body["signature_b64"] = base64.b64encode(b"garbage").decode()
    assert client.post("/api/v1/signatures/verify", headers=auth("clerk-token"), json=body).json() == {"valid": False}


def test_verify_endpoint_requires_authentication(client):
    r = client.post("/api/v1/signatures/verify", json={
        "public_key_pem": "x", "canonical_payload": "x", "signature_b64": "x",
    })
    assert r.status_code == 401
