from __future__ import annotations

import re
from typing import Any, Protocol

import anyio

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.models import CurrentUser, UserRole
from app.integrations.supabase import SupabaseGateway
from app.services.authorization import AuthorizationService

# Versioned so a future payload shape change can't be misread as this one.
# The whole point of anchoring is that this exact string, sitting in a
# public transaction's calldata forever, is what an independent verifier
# reads back - it is deliberately plain text, not binary-packed.
ANCHOR_PREFIX = "NYAYAVAULT-ANCHOR-V1"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _build_anchor_payload(sequence: int, entry_hash: str) -> bytes:
    return f"{ANCHOR_PREFIX}:{sequence}:{entry_hash}".encode("utf-8")


def _parse_anchor_payload(data: bytes) -> tuple[int, str]:
    text = data.decode("utf-8")
    prefix, _, rest = text.partition(":")
    if prefix != ANCHOR_PREFIX:
        raise ValueError(f"Not a Nyaya Vault anchor payload (got prefix {prefix!r}).")
    sequence_text, _, entry_hash = rest.partition(":")
    if not sequence_text.isdigit() or not _HEX64.match(entry_hash):
        raise ValueError("Malformed anchor payload.")
    return int(sequence_text), entry_hash


class AnchorClient(Protocol):
    """What BlockchainAnchorService needs from a chain client - kept as its
    own small interface (same shape as assistant.py's LlmClient) so tests
    can inject a fake and never touch a real RPC endpoint or spend real
    (even if testnet) gas just to exercise the surrounding logic."""

    async def submit_anchor(self, *, sequence: int, entry_hash: str) -> dict[str, Any]: ...
    async def fetch_onchain_record(self, tx_hash: str) -> dict[str, Any]: ...


class PolygonAnchorClient:
    """Sends a zero-value, self-addressed transaction whose data field is
    the anchor payload. No smart contract is deployed or needed: once
    mined, the payload is permanently readable by anyone from the
    transaction's calldata via any public RPC or block explorer - that
    public, independently-hosted record is the actual security property
    being added here, not anything clever in this class.

    web3/eth_account are imported lazily (inside the methods, not at module
    import time) so the rest of the app - and ENABLE_BLOCKCHAIN_ANCHOR=false,
    the default - never depends on them being installed correctly against a
    live network, mirroring how vision.py defers importing ultralytics.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self):
        from web3 import Web3

        if not self.settings.blockchain_rpc_url:
            raise ConflictError(
                "Blockchain anchoring is not configured - set BLOCKCHAIN_RPC_URL.",
                details={"reason": "BLOCKCHAIN_ANCHOR_NOT_CONFIGURED"},
            )
        return Web3(Web3.HTTPProvider(self.settings.blockchain_rpc_url, request_kwargs={"timeout": 30}))

    def _submit_sync(self, sequence: int, entry_hash: str) -> dict[str, Any]:
        from eth_account import Account

        if not self.settings.blockchain_private_key:
            raise ConflictError(
                "Blockchain anchoring is not configured - set BLOCKCHAIN_PRIVATE_KEY.",
                details={"reason": "BLOCKCHAIN_ANCHOR_NOT_CONFIGURED"},
            )
        w3 = self._client()
        account = Account.from_key(self.settings.blockchain_private_key)
        to_address = self.settings.blockchain_anchor_to_address or account.address
        payload = _build_anchor_payload(sequence, entry_hash)

        tx = {
            "from": account.address,
            "to": to_address,
            "value": 0,
            "data": payload,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": self.settings.blockchain_chain_id,
            "gas": self.settings.blockchain_gas_limit,
            "gasPrice": w3.eth.gas_price,
        }
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = "0x" + tx_hash.hex().removeprefix("0x")

        status, block_number = "PENDING", None
        try:
            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.settings.blockchain_confirmation_timeout_seconds,
            )
            block_number = receipt.blockNumber
            status = "CONFIRMED" if receipt.status == 1 else "FAILED"
        except Exception:
            # Not fatal - the transaction was broadcast and has a real hash;
            # it just hasn't been mined within our wait window yet. The
            # explorer link lets a human check on it later.
            pass

        return {
            "provider": "polygon_amoy" if self.settings.blockchain_chain_id == 80002 else f"chain_{self.settings.blockchain_chain_id}",
            "tx_hash": tx_hash_hex,
            "chain_id": self.settings.blockchain_chain_id,
            "status": status,
            "block_number": block_number,
            "explorer_url": f"{self.settings.blockchain_explorer_tx_base_url.rstrip('/')}/{tx_hash_hex}",
        }

    async def submit_anchor(self, *, sequence: int, entry_hash: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(self._submit_sync, sequence, entry_hash)

    def _fetch_sync(self, tx_hash: str) -> dict[str, Any]:
        w3 = self._client()
        try:
            tx = w3.eth.get_transaction(tx_hash)
        except Exception as exc:
            raise NotFoundError(f"Transaction {tx_hash} was not found on-chain.") from exc
        raw = bytes(tx["input"])
        try:
            sequence, entry_hash = _parse_anchor_payload(raw)
        except ValueError as exc:
            raise ConflictError(f"On-chain transaction data is not a valid anchor payload: {exc}") from exc
        return {"sequence": sequence, "entry_hash": entry_hash}

    async def fetch_onchain_record(self, tx_hash: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(self._fetch_sync, tx_hash)


class BlockchainAnchorService:
    """Orchestrates anchoring the audit chain's current head to a public
    blockchain and re-verifying past anchors against it later.

    Honest scope, worth stating plainly rather than letting the feature
    name imply more than it does: this closes the specific gap where a
    service_role-level compromise of *this app's own database* could
    rewrite audit history with nothing outside Postgres to catch it - once
    a sequence is anchored, its entry_hash is independently, publicly
    recorded and anyone can recompute and compare. It is a single backend
    writing to a public chain it does not otherwise control, not a
    multi-party consensus ledger; the anchoring account's private key is
    still a single point of trust for *creating new* anchors (though not
    for detecting tampering with ones already made).
    """

    def __init__(self, gateway: SupabaseGateway, settings: Settings, *, chain_client: AnchorClient | None = None) -> None:
        self.gateway = gateway
        self.settings = settings
        self.authz = AuthorizationService(gateway)
        self.chain_client: AnchorClient = chain_client or PolygonAnchorClient(settings)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.enable_blockchain_anchor and self.settings.blockchain_private_key and self.settings.blockchain_rpc_url)

    async def _chain_head(self) -> dict[str, Any]:
        rows = await self.gateway.service_table(
            "GET", "audit_logs", params={"select": "sequence,entry_hash", "order": "sequence.desc", "limit": "1"},
        )
        if not rows:
            raise ConflictError("Audit chain is empty - nothing to anchor yet.")
        return rows[0]

    async def create_anchor(self, user: CurrentUser) -> dict[str, Any]:
        await self.authz.require_role(user, UserRole.ADMIN)
        if not self.enabled:
            raise ConflictError(
                "Blockchain anchoring is not configured on this server - set ENABLE_BLOCKCHAIN_ANCHOR, "
                "BLOCKCHAIN_RPC_URL and BLOCKCHAIN_PRIVATE_KEY.",
                details={"reason": "BLOCKCHAIN_ANCHOR_NOT_CONFIGURED"},
            )
        head = await self._chain_head()
        sequence, entry_hash = int(head["sequence"]), str(head["entry_hash"])

        submission = await self.chain_client.submit_anchor(sequence=sequence, entry_hash=entry_hash)

        result = await self.gateway.rpc_service(
            "backend_record_integrity_anchor",
            {
                "p_actor_user_id": user.id,
                "p_audit_sequence": sequence,
                "p_audit_entry_hash": entry_hash,
                "p_anchor_provider": submission["provider"],
                "p_anchor_reference": submission["tx_hash"],
                "p_chain_id": submission["chain_id"],
                "p_tx_status": submission["status"],
                "p_explorer_url": submission.get("explorer_url"),
            },
        )
        if isinstance(result, list):
            result = result[0] if result else {}
        if not result or not result.get("ok"):
            raise ConflictError(str((result or {}).get("error") or "Failed to record the anchor."))

        return {
            "anchor_id": result["anchor_id"],
            "audit_sequence": sequence,
            "audit_entry_hash": entry_hash,
            **submission,
        }

    async def list_anchors(self, user: CurrentUser, limit: int = 25) -> list[dict[str, Any]]:
        return await self.gateway.service_table(
            "GET", "integrity_anchors",
            params={"select": "*", "order": "anchored_at.desc", "limit": str(max(1, min(limit, 100)))},
        ) or []

    async def verify_anchor(self, user: CurrentUser, anchor_id: str) -> dict[str, Any]:
        rows = await self.gateway.service_table(
            "GET", "integrity_anchors", params={"id": f"eq.{anchor_id}", "select": "*", "limit": "1"},
        )
        if not rows:
            raise NotFoundError("Anchor not found.")
        anchor = rows[0]

        onchain = await self.chain_client.fetch_onchain_record(anchor["anchor_reference"])

        current_rows = await self.gateway.service_table(
            "GET", "audit_logs",
            params={"sequence": f"eq.{onchain['sequence']}", "select": "entry_hash", "limit": "1"},
        )
        current_hash = current_rows[0]["entry_hash"] if current_rows else None

        matches_anchor_record = onchain["sequence"] == anchor["audit_sequence"] and onchain["entry_hash"] == anchor["audit_entry_hash"]
        matches_live_chain = current_hash is not None and current_hash == onchain["entry_hash"]

        return {
            "anchor_id": anchor["id"],
            "audit_sequence": anchor["audit_sequence"],
            "onchain_sequence": onchain["sequence"],
            "onchain_entry_hash": onchain["entry_hash"],
            "current_entry_hash": current_hash,
            # The record we stored ourselves matches what's on-chain - sanity
            # check on our own bookkeeping, not independent proof by itself.
            "anchor_record_matches_chain_data": matches_anchor_record,
            # The load-bearing check: today's live database, at the anchored
            # sequence, still hashes to exactly what a public, independently
            # hosted blockchain has recorded since the anchor was made.
            "live_database_matches_onchain_record": matches_live_chain,
            "verified": matches_anchor_record and matches_live_chain,
        }
