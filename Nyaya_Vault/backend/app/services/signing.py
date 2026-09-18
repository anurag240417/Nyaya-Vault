"""
Real cryptographic signing for certificates and legal notices (option B
from the digital-signature design discussion, replacing the plain typed-name
stamp in signature_stamp.py). Each user gets an ECDSA P-256 keypair, issued
on first use, and every certificate/notice is signed over the exact record
being certified - not just labelled with a name.

Honest scope: the private key is generated and held **by this backend**,
encrypted at rest, because PDF generation happens entirely server-side.
That means the signature proves "the backend, acting for this authenticated
user account, attested to exactly this record at this time" - a real,
independently-verifiable cryptographic claim, and a large step up from an
unsigned typed name. It is NOT proof that only the human holds the private
key independent of the backend (true non-repudiation would need the key
held client-side, in a hardware token, or in an HSM - out of scope here).
Anyone can still verify a signature completely offline, with no dependency
on this system being online or trustworthy at verification time: recompute
SHA-256 of the canonical payload printed on the document, and check it
against the signature and public key printed alongside it using any
standard ECDSA implementation.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import Settings
from app.core.models import CurrentUser
from app.integrations.supabase import SupabaseGateway

ALGORITHM = "ECDSA-P256-SHA256"


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic serialization: same payload always produces the exact
    same bytes to sign/verify, regardless of dict insertion order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fernet(settings: Settings) -> Fernet:
    key_material = hashlib.sha256(settings.resolved_signing_key_encryption_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def fingerprint(public_key_pem: str) -> str:
    """Short, human-comparable stand-in for the full public key - the SHA-256
    of the key's DER encoding, hex, truncated. Printed on documents and
    profile pages; the full PEM is what's actually needed to verify."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()[:24]


def verify_signature(*, public_key_pem: str, canonical_payload: str, signature_b64: str) -> bool:
    """Pure function, no database/network - exactly what an outside party
    would run to verify a certificate independently of this system."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, canonical_payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


class SigningService:
    def __init__(self, gateway: SupabaseGateway, settings: Settings) -> None:
        self.gateway = gateway
        self.settings = settings

    async def _load_key_row(self, user_id: str) -> dict[str, Any] | None:
        rows = await self.gateway.service_table(
            "GET", "user_signing_keys",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": "1"},
        )
        return rows[0] if rows else None

    async def _get_or_create_key(self, user_id: str) -> tuple[str, Any]:
        """Returns (public_key_pem, private_key_object). Generates a new
        keypair on first use for this user; a concurrent first use races
        safely via backend_store_signing_key's on-conflict-do-nothing."""
        row = await self._load_key_row(user_id)
        if row is None:
            private_key = ec.generate_private_key(ec.SECP256R1())
            public_pem = private_key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
            private_pem = private_key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
            )
            encrypted = _fernet(self.settings).encrypt(private_pem).decode("utf-8")

            result = await self.gateway.rpc_service(
                "backend_store_signing_key",
                {
                    "p_user_id": user_id, "p_public_key_pem": public_pem,
                    "p_private_key_encrypted": encrypted, "p_algorithm": ALGORITHM,
                },
            )
            if isinstance(result, list):
                result = result[0] if result else {}
            if not result or not result.get("ok"):
                raise RuntimeError(str((result or {}).get("error") or "Failed to issue a signing key."))
            row = result

        try:
            private_pem = _fernet(self.settings).decrypt(row["private_key_encrypted"].encode("utf-8"))
        except InvalidToken as exc:
            raise RuntimeError(
                "Could not decrypt this user's signing key - SIGNING_KEY_ENCRYPTION_SECRET (or the "
                "Supabase secret key it falls back to) has changed since this key was issued."
            ) from exc
        private_key = serialization.load_pem_private_key(private_pem, password=None)
        return row["public_key_pem"], private_key

    async def public_key_info(self, user: CurrentUser) -> dict[str, Any]:
        """Never touches/returns the encrypted private key - only what's
        safe to show the user themselves (their own public key)."""
        public_pem, _ = await self._get_or_create_key(user.id)
        row = await self._load_key_row(user.id)
        return {
            "public_key_pem": public_pem,
            "algorithm": (row or {}).get("algorithm", ALGORITHM),
            "fingerprint": fingerprint(public_pem),
            "created_at": (row or {}).get("created_at"),
        }

    async def sign_for_user(self, user: CurrentUser, *, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        public_pem, private_key = await self._get_or_create_key(user.id)
        full_payload = {
            "purpose": purpose,
            "signer_user_id": user.id,
            "signer_username": user.username,
            "signer_role": user.role.value,
            "signed_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        canonical = canonical_json(full_payload)
        signature = private_key.sign(canonical.encode("utf-8"), ec.ECDSA(hashes.SHA256()))

        return {
            "algorithm": ALGORITHM,
            "public_key_pem": public_pem,
            "canonical_payload": canonical,
            "signature_b64": base64.b64encode(signature).decode("ascii"),
            "fingerprint": fingerprint(public_pem),
            "signer_username": user.username,
            "signed_at": full_payload["signed_at"],
        }
