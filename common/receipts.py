"""Receipts and the audit ledger. A receipt is the unit of accountability:
who was asked, what exactly, what came back, when, and what it cost."""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from common.signing import event_hash, sign, PUBLIC_KEY_B64


def sha(obj: Any) -> str:
    raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class Receipt:
    run_id: str
    task_id: str
    agent_name: str
    agent_url: str
    card_hash: str
    input_hash: str
    output_hash: str = ""
    kind: str = "delegate"          # probe | delegate | verify
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    latency_ms: Optional[int] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    status: str = "pending"          # pending | ok | failed | rejected
    note: str = ""
    receipt_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def close(self, output: Any, status: str = "ok", note: str = "", tokens_in: int = 0, tokens_out: int = 0):
        self.ended_at = time.time()
        self.latency_ms = int((self.ended_at - self.started_at) * 1000)
        self.output_hash = sha(output)
        self.status, self.note = status, note
        self.tokens_in, self.tokens_out = tokens_in, tokens_out
        # Gemini 2.5 Flash list price, USD per 1M tokens (input 0.30, output 2.50); indicative only.
        self.cost_usd = round(tokens_in * 0.30e-6 + tokens_out * 2.50e-6, 6)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


class Ledger:
    """Append-only event log for one run. Events are plain dicts; receipts are one event kind."""

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or uuid.uuid4().hex[:10]
        self.events: list[dict] = []
        self._subs: list = []

    def emit(self, kind: str, **data):
        ev = {"ts": time.time(), "run_id": self.run_id, "kind": kind, "seq": len(self.events), **data}
        ev["prev"] = self.events[-1]["hash"] if self.events else ""
        if kind == "receipt":
            ev["sig"] = sign(ev["receipt"])
        ev["hash"] = event_hash(ev)
        self.events.append(ev)
        for q in list(self._subs):
            try:
                q.put_nowait(ev)
            except Exception:
                pass
        return ev

    def receipt(self, r: Receipt):
        return self.emit("receipt", receipt=r.to_dict())

    def subscribe(self, q):
        self._subs.append(q)

    def unsubscribe(self, q):
        if q in self._subs:
            self._subs.remove(q)

    def receipts(self) -> list[dict]:
        return [e["receipt"] for e in self.events if e["kind"] == "receipt"]

    def to_json(self) -> str:
        return json.dumps({"run_id": self.run_id, "public_key": PUBLIC_KEY_B64, "events": self.events}, indent=2, default=str)
