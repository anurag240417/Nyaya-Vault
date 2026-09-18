from __future__ import annotations

from typing import Any

from tests.conftest import auth
from tests.test_api_end_to_end import create_case


class FakeAnchorClient:
    """Records every call instead of hitting a real RPC endpoint or
    spending real (even testnet) gas - see FakeLlmClient in
    test_assistant.py for the same pattern applied to the AI assistant."""

    def __init__(self) -> None:
        self.submitted: list[dict[str, Any]] = []
        self._records: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def submit_anchor(self, *, sequence: int, entry_hash: str) -> dict[str, Any]:
        self._counter += 1
        tx_hash = f"0x{'ab' * 30}{self._counter:04d}"
        self.submitted.append({"sequence": sequence, "entry_hash": entry_hash, "tx_hash": tx_hash})
        self._records[tx_hash] = {"sequence": sequence, "entry_hash": entry_hash}
        return {
            "provider": "polygon_amoy", "tx_hash": tx_hash, "chain_id": 80002,
            "status": "CONFIRMED", "block_number": 999, "explorer_url": f"https://amoy.polygonscan.com/tx/{tx_hash}",
        }

    async def fetch_onchain_record(self, tx_hash: str) -> dict[str, Any]:
        return self._records[tx_hash]


def enable_anchoring(client) -> FakeAnchorClient:
    service = client.app.state.blockchain_anchor
    service.settings.enable_blockchain_anchor = True
    service.settings.blockchain_rpc_url = "http://fake-rpc.invalid"
    service.settings.blockchain_private_key = "0x" + "11" * 32
    fake = FakeAnchorClient()
    service.chain_client = fake
    return fake


def test_anchoring_is_disabled_by_default(client):
    listing = client.get("/api/v1/integrity/anchors", headers=auth("admin-token"))
    assert listing.status_code == 200, listing.text
    assert listing.json() == {"enabled": False, "anchors": []}

    created = client.post("/api/v1/integrity/anchors", headers=auth("admin-token"))
    assert created.status_code == 409
    assert created.json()["details"]["reason"] == "BLOCKCHAIN_ANCHOR_NOT_CONFIGURED"


def test_only_admin_can_create_an_anchor(client, gateway):
    fake = enable_anchoring(client)
    create_case(client)  # generates at least one audit row (CASE_CREATED)

    denied = client.post("/api/v1/integrity/anchors", headers=auth("io-token"))
    assert denied.status_code == 403
    assert fake.submitted == []  # never reached the chain client


def test_empty_audit_chain_cannot_be_anchored(client):
    enable_anchoring(client)
    r = client.post("/api/v1/integrity/anchors", headers=auth("admin-token"))
    assert r.status_code == 409


def test_admin_can_create_anchor_and_it_is_recorded_and_audited(client, gateway):
    fake = enable_anchoring(client)
    create_case(client)

    head = sorted(gateway.tables["audit_logs"], key=lambda r: r["sequence"])[-1]

    r = client.post("/api/v1/integrity/anchors", headers=auth("admin-token"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audit_sequence"] == head["sequence"]
    assert body["audit_entry_hash"] == head["entry_hash"]
    assert body["tx_hash"] == fake.submitted[0]["tx_hash"]
    assert body["status"] == "CONFIRMED"
    assert body["explorer_url"].startswith("https://amoy.polygonscan.com/tx/")

    actions = [a["action"] for a in gateway.tables["audit_logs"]]
    assert "AUDIT_CHAIN_ANCHORED" in actions

    listing = client.get("/api/v1/integrity/anchors", headers=auth("admin-token")).json()
    assert listing["enabled"] is True
    assert listing["anchors"][0]["id"] == body["anchor_id"]
    assert listing["anchors"][0]["anchor_reference"] == fake.submitted[0]["tx_hash"]


def test_verify_anchor_confirms_an_untampered_chain(client, gateway):
    enable_anchoring(client)
    create_case(client)
    anchor_id = client.post("/api/v1/integrity/anchors", headers=auth("admin-token")).json()["anchor_id"]

    r = client.get(f"/api/v1/integrity/anchors/{anchor_id}/verify", headers=auth("io-token"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["anchor_record_matches_chain_data"] is True
    assert body["live_database_matches_onchain_record"] is True


def test_verify_anchor_detects_a_rewritten_audit_row(client, gateway):
    """The whole point of the feature: a service_role-level rewrite of
    audit_logs after anchoring must be detectable by comparing against the
    independently-hosted (here, faked) on-chain record - not against
    another table in the same database, which a rewrite could edit too."""
    enable_anchoring(client)
    create_case(client)
    anchor = client.post("/api/v1/integrity/anchors", headers=auth("admin-token")).json()

    # Simulate a direct, out-of-band database rewrite of the anchored row.
    for row in gateway.tables["audit_logs"]:
        if row["sequence"] == anchor["audit_sequence"]:
            row["entry_hash"] = "f" * 64
            row["action"] = "CASE_CREATED"  # pretend the tampered content is otherwise unremarkable

    r = client.get(f"/api/v1/integrity/anchors/{anchor['anchor_id']}/verify", headers=auth("admin-token"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is False
    assert body["live_database_matches_onchain_record"] is False
    # Our own bookkeeping row is untouched - only the audit_logs row was rewritten.
    assert body["anchor_record_matches_chain_data"] is True


def test_verify_unknown_anchor_returns_404(client):
    enable_anchoring(client)
    r = client.get("/api/v1/integrity/anchors/00000000-0000-0000-0000-000000000000/verify", headers=auth("admin-token"))
    assert r.status_code == 404
