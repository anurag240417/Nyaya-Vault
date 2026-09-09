from __future__ import annotations

from tests.conftest import auth
from tests.test_api_end_to_end import create_case


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