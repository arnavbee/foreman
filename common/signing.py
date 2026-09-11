"""Tamper-evident ledger: every event carries the hash of the previous one (a chain), and every receipt is
signed with Foreman's Ed25519 key. Anyone holding the public key can verify an audit file offline, and any
edited number breaks the chain at that event. The key is generated per deployment unless FOREMAN_SIGNING_KEY
(base64 32-byte seed) is set, so signatures stay stable across Cloud Run instances."""
from __future__ import annotations
import base64, json, os, hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

_seed = os.getenv("FOREMAN_SIGNING_KEY")
_priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(_seed)) if _seed else Ed25519PrivateKey.generate()
PUBLIC_KEY_B64 = base64.b64encode(_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def event_hash(ev: dict) -> str:
    body = {k: v for k, v in ev.items() if k not in ("hash", "sig")}
    return hashlib.sha256(canonical(body)).hexdigest()


def sign(payload: dict) -> str:
    return base64.b64encode(_priv.sign(canonical(payload))).decode()


def verify_chain(ledger: dict, public_key_b64: str | None = None) -> dict:
    """Recompute every hash and signature. Returns {ok, checked, first_bad}."""
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64 or ledger.get("public_key") or PUBLIC_KEY_B64))
    prev = ""
    for i, ev in enumerate(ledger.get("events", [])):
        if ev.get("prev") != prev:
            return {"ok": False, "checked": i, "first_bad": i, "why": "chain break: prev hash mismatch"}
        if event_hash(ev) != ev.get("hash"):
            return {"ok": False, "checked": i, "first_bad": i, "why": "event content altered: hash mismatch"}
        if ev.get("kind") == "receipt":
            try:
                pub.verify(base64.b64decode(ev["sig"]), canonical(ev["receipt"]))
            except Exception:
                return {"ok": False, "checked": i, "first_bad": i, "why": "receipt signature invalid"}
        prev = ev["hash"]
    return {"ok": True, "checked": len(ledger.get("events", [])), "first_bad": None}
