from __future__ import annotations

from tests.conftest import auth
from tests.test_api_end_to_end import create_case, make_pdf


def add_statement(client, case_id, **kwargs):
    body = {
        "person_name": "Rakesh Sharma",
        "location_name": "City A",
        "window_start": "2026-03-12T14:00:00Z",
        "window_end": "2026-03-12T14:30:00Z",
        "duration_minutes": 30,
        **kwargs,
    }
    return client.post(f"/api/v1/cases/{case_id}/timeline/statements", headers=auth("admin-token"), json=body)


def test_contradictory_statements_are_flagged(client):
    case = create_case(client)
    case_id = case["id"]

    r1 = add_statement(client, case_id, location_name="City A",
                        window_start="2026-03-12T14:00:00Z", window_end="2026-03-12T14:30:00Z")
    assert r1.status_code == 201, r1.text
    assert r1.json()["contradiction_detected"] is False

    # Same person, a different city, only 15 minutes later - a plain
    # double-booking even with zero known travel time between the cities.
    r2 = add_statement(client, case_id, location_name="City B",
                        window_start="2026-03-12T14:15:00Z", window_end="2026-03-12T14:45:00Z")
    assert r2.status_code == 201, r2.text
    assert r2.json()["contradiction_detected"] is True

    conflicts = client.get(f"/api/v1/cases/{case_id}/timeline/conflicts", headers=auth("admin-token"))
    assert conflicts.status_code == 200
    body = conflicts.json()
    assert len(body) == 1
    assert body[0]["person_name"] == "Rakesh Sharma"
    assert body[0]["status"] == "OPEN"
    assert set(body[0]["statement_ids"]) == {r1.json()["statement"]["id"], r2.json()["statement"]["id"]}


def test_consistent_statements_are_not_flagged(client):
    case = create_case(client)
    case_id = case["id"]

    add_statement(client, case_id, location_name="City A",
                  window_start="2026-03-12T14:00:00Z", window_end="2026-03-12T14:30:00Z")
    # Same two cities as the contradiction test, but hours apart - plenty
    # of time to travel even with zero recorded travel time.
    r2 = add_statement(client, case_id, location_name="City B",
                        window_start="2026-03-12T20:00:00Z", window_end="2026-03-12T21:00:00Z")
    assert r2.json()["contradiction_detected"] is False

    conflicts = client.get(f"/api/v1/cases/{case_id}/timeline/conflicts", headers=auth("admin-token"))
    assert conflicts.json() == []


def test_travel_time_can_turn_a_feasible_pair_into_a_contradiction(client):
    case = create_case(client)
    case_id = case["id"]

    add_statement(client, case_id, location_name="City A",
                  window_start="2026-03-12T14:00:00Z", window_end="2026-03-12T14:30:00Z")
    add_statement(client, case_id, location_name="City B",
                  window_start="2026-03-12T15:00:00Z", window_end="2026-03-12T15:30:00Z")

    # 30 minutes apart is fine with no known travel time - not flagged yet.
    assert client.get(f"/api/v1/cases/{case_id}/timeline/conflicts", headers=auth("admin-token")).json() == []

    # Now record that City A -> City B is actually a 3 hour drive. The
    # existing pair should be re-evaluated and flagged retroactively.
    travel = client.post(
        f"/api/v1/cases/{case_id}/timeline/travel-times",
        headers=auth("admin-token"),
        json={"location_a": "City A", "location_b": "City B", "minutes": 180},
    )
    assert travel.status_code == 201, travel.text

    conflicts = client.get(f"/api/v1/cases/{case_id}/timeline/conflicts", headers=auth("admin-token")).json()
    assert len(conflicts) == 1
    assert conflicts[0]["person_name"] == "Rakesh Sharma"


def test_different_people_do_not_interfere(client):
    case = create_case(client)
    case_id = case["id"]

    add_statement(client, case_id, person_name="Rakesh Sharma", location_name="City A",
                  window_start="2026-03-12T14:00:00Z", window_end="2026-03-12T14:30:00Z")
    r2 = add_statement(client, case_id, person_name="Suresh Kumar", location_name="City B",
                        window_start="2026-03-12T14:15:00Z", window_end="2026-03-12T14:45:00Z")

    # Different people, so this is not a contradiction even though the
    # windows/locations look like the earlier contradiction test.
    assert r2.json()["contradiction_detected"] is False
    assert client.get(f"/api/v1/cases/{case_id}/timeline/conflicts", headers=auth("admin-token")).json() == []


def test_timeline_statement_requires_case_access(client):
    case = create_case(client)  # created by admin, not otherio
    response = add_statement(client, case["id"])
    assert response.status_code == 201
    denied = client.post(
        f"/api/v1/cases/{case['id']}/timeline/statements",
        headers=auth("otherio-token"),
        json={
            "person_name": "X", "location_name": "Y",
            "window_start": "2026-03-12T14:00:00Z", "window_end": "2026-03-12T14:30:00Z",
        },
    )
    assert denied.status_code == 403


def _seed_document_with_entities(gateway, case_id, *, entities, page_number=1, confirmed=True):
    """Seeds a document/version/entities directly in the fake gateway - a
    real upload would go through OCR/NER, which is unnecessary weight for
    testing the suggestion-grouping logic itself."""
    from tests.fake_gateway import uid, now_iso

    doc_id = uid()
    version_id = uid()
    gateway.tables["documents"].append({
        "id": doc_id, "case_id": case_id, "title": "FIR Annexure Statement",
        "document_type": "STATEMENT", "clearance_level": "RESTRICTED",
        "current_version_number": 1, "created_by": gateway.tokens["admin-token"],
        "created_at": now_iso(),
    })
    gateway.tables["document_versions"].append({
        "id": version_id, "document_id": doc_id, "version_number": 1,
        "storage_key": "x", "sha256": "x", "size_bytes": 1, "mime_type": "application/pdf",
        "change_summary": None, "processing_status": "COMPLETED", "processing_error": None,
        "extracted_text": None, "ocr_used": False, "created_by": gateway.tokens["admin-token"],
        "created_at": now_iso(),
    })
    for entity_type, value in entities:
        gateway.tables["document_entities"].append({
            "id": uid(), "document_version_id": version_id, "entity_type": entity_type,
            "value": value, "confidence": 0.9, "page_number": page_number,
            "start_offset": 0, "end_offset": len(value), "confirmed": confirmed,
            "created_at": now_iso(),
        })
    return doc_id, version_id


def test_suggestions_generated_from_confirmed_entities_are_not_confirmed(client, gateway):
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ])

    r = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    assert r.status_code == 201, r.text
    suggestions = r.json()
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["status"] == "SUGGESTED"
    assert s["person_name"] == "Ramesh Kumar"
    assert s["location_name"] == "Nagpur"
    assert s["window_start"].startswith("2026-03-12")

    # A suggestion must never show up as a conflict on its own - it hasn't
    # been confirmed by a human yet.
    assert client.get(f"/api/v1/cases/{case['id']}/timeline/conflicts", headers=auth("admin-token")).json() == []


def test_suggestions_ignore_unconfirmed_entities(client, gateway):
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ], confirmed=False)

    r = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    assert r.status_code == 201
    assert r.json() == []


def test_confirming_a_suggestion_feeds_the_solver(client, gateway):
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ], page_number=1)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Pune"), ("DATE", "12/03/2026"),
    ], page_number=1)

    r = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    suggestions = r.json()
    assert len(suggestions) == 2

    # Still nothing confirmed - no conflict yet even though the underlying
    # facts (same person, same day, two different cities) would contradict.
    assert client.get(f"/api/v1/cases/{case['id']}/timeline/conflicts", headers=auth("admin-token")).json() == []

    for s in suggestions:
        confirm = client.post(
            f"/api/v1/cases/{case['id']}/timeline/statements/{s['id']}/confirm",
            headers=auth("admin-token"),
        )
        assert confirm.status_code == 200, confirm.text

    # Full-day windows alone (only a DATE was extracted, no time-of-day) are
    # deliberately weak evidence - the solver can fit "somewhere in Nagpur"
    # and "somewhere in Pune" into the same 24 hours with zero known travel
    # time, so no conflict yet. Recording that the two are genuinely far
    # apart (Nagpur-Pune is ~720km, no real trip is a few minutes) is what
    # sharpens this into an actual contradiction - the realistic workflow.
    assert client.get(f"/api/v1/cases/{case['id']}/timeline/conflicts", headers=auth("admin-token")).json() == []

    travel_ab = client.post(
        f"/api/v1/cases/{case['id']}/timeline/travel-times",
        headers=auth("admin-token"),
        json={"location_a": "Nagpur", "location_b": "Pune", "minutes": 1500},
    )
    assert travel_ab.status_code == 201, travel_ab.text
    travel_ba = client.post(
        f"/api/v1/cases/{case['id']}/timeline/travel-times",
        headers=auth("admin-token"),
        json={"location_a": "Pune", "location_b": "Nagpur", "minutes": 1500},
    )
    assert travel_ba.status_code == 201, travel_ba.text

    conflicts = client.get(f"/api/v1/cases/{case['id']}/timeline/conflicts", headers=auth("admin-token")).json()
    assert len(conflicts) == 1
    assert conflicts[0]["person_name"] == "Ramesh Kumar"


def test_rejecting_a_suggestion_removes_it(client, gateway):
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ])
    suggestions = client.post(
        f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"),
    ).json()
    statement_id = suggestions[0]["id"]

    reject = client.delete(
        f"/api/v1/cases/{case['id']}/timeline/statements/{statement_id}", headers=auth("admin-token"),
    )
    assert reject.status_code == 204

    remaining = client.get(f"/api/v1/cases/{case['id']}/timeline/statements", headers=auth("admin-token")).json()
    assert remaining == []


def test_regenerating_suggestions_does_not_duplicate(client, gateway):
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ])
    first = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    assert len(first.json()) == 1
    second = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    assert second.json() == []


def test_confirming_entities_automatically_generates_suggestions_no_manual_scan(client, gateway):
    """The whole point of the auto-trigger: an officer reviewing extracted
    entities on the normal Documents > Entities screen should never need to
    know a separate 'scan for candidates' step exists. Confirming entities
    through the real /entities/review endpoint (not seeding + calling
    generate directly) must produce a suggestion on its own."""
    case = create_case(client)
    doc_id, version_id = _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"), ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ], confirmed=False)
    entity_ids = [e["id"] for e in gateway.tables["document_entities"] if e["document_version_id"] == version_id]

    # Zero suggestions before confirmation - entities are still unconfirmed.
    assert client.get(f"/api/v1/cases/{case['id']}/timeline/statements", headers=auth("admin-token")).json() == []

    review = client.post(
        f"/api/v1/documents/{doc_id}/entities/review", headers=auth("admin-token"),
        json={"confirmed_ids": entity_ids, "rejected_ids": []},
    )
    assert review.status_code == 200, review.text

    # No call to /timeline/suggestions/generate was made - this must have
    # happened automatically as a side effect of the confirmation itself.
    statements = client.get(f"/api/v1/cases/{case['id']}/timeline/statements", headers=auth("admin-token")).json()
    assert len(statements) == 1
    assert statements[0]["status"] == "SUGGESTED"
    assert statements[0]["person_name"] == "Ramesh Kumar"

    # Still just a suggestion - it must not have auto-confirmed itself.
    assert client.get(f"/api/v1/cases/{case['id']}/timeline/conflicts", headers=auth("admin-token")).json() == []


def test_multi_page_document_entities_are_grouped_across_pages(client, gateway):
    """A person named on page 1 and a location named on page 3 of the same
    document must still be paired - the co-occurrence heuristic is per
    document, not per page, precisely so a real multi-page FIR isn't missed."""
    case = create_case(client)
    _seed_document_with_entities(gateway, case["id"], entities=[
        ("PERSON", "Ramesh Kumar"),
    ], page_number=1)
    doc_id, version_id = _seed_document_with_entities(gateway, case["id"], entities=[
        ("LOCATION", "Nagpur"), ("DATE", "12/03/2026"),
    ], page_number=3)
    # Move the first seeded document's entity onto the SAME document as the
    # second seed, so this genuinely tests one multi-page document rather
    # than two separate documents (which the earlier cross-document test
    # already covers).
    for row in gateway.tables["document_entities"]:
        if row["value"] == "Ramesh Kumar":
            row["document_version_id"] = version_id
            row["page_number"] = 1

    r = client.post(f"/api/v1/cases/{case['id']}/timeline/suggestions/generate", headers=auth("admin-token"))
    assert r.status_code == 201, r.text
    suggestions = r.json()
    assert len(suggestions) == 1
    assert "p.1" in suggestions[0]["source_excerpt"]
    assert "p.3" in suggestions[0]["source_excerpt"]