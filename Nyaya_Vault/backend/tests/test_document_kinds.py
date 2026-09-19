from __future__ import annotations

from io import BytesIO

from PIL import Image

from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_mp4, make_pdf


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, "PNG")
    return buf.getvalue()


def _upload(client, case_id, title, filename, data, mime):
    r = client.post(
        f"/api/v1/cases/{case_id}/documents", headers=auth("admin-token"),
        data={"title": title, "clearance_level": "RESTRICTED"}, files={"file": (filename, data, mime)},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["documentId"]


def test_document_list_reports_the_real_file_type_of_each_document(client):
    case = create_case(client)
    pdf = _upload(client, case["id"], "Statement", "s.pdf", make_pdf("text"), "application/pdf")
    img = _upload(client, case["id"], "Scene photo", "p.png", _png(), "image/png")
    vid = _upload(client, case["id"], "Crime site video", "v.mp4", make_mp4(), "video/mp4")

    rows = client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token")).json()
    by_id = {r["id"]: r["mime_type"] for r in rows}
    assert by_id == {pdf: "application/pdf", img: "image/png", vid: "video/mp4"}


def test_mime_type_follows_the_current_version(client):
    case = create_case(client)
    doc = _upload(client, case["id"], "Evidence", "e.pdf", make_pdf("v1"), "application/pdf")
    r = client.post(
        f"/api/v1/documents/{doc}/versions", headers=auth("admin-token"),
        data={"change_summary": "replaced with a photo"}, files={"file": ("e.png", _png(), "image/png")},
    )
    assert r.status_code in (200, 201), r.text
    rows = client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token")).json()
    assert rows[0]["mime_type"] == "image/png"


def test_empty_case_still_lists_cleanly(client):
    case = create_case(client)
    assert client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token")).json() == []
