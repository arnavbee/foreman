"""Track record per delegate across runs: vetting scores, jobs, verified results. Foreman's memory of who
has earned trust. JSON on disk for the demo; the same shape drops into Firestore unchanged."""
from __future__ import annotations
import json, os, time, threading

PATH = os.getenv("SCORECARDS_PATH", os.path.join(os.path.dirname(__file__), "..", "runs", "scorecards.json"))
_lock = threading.Lock()


def _load() -> dict:
    try:
        return json.load(open(PATH))
    except Exception:
        return {}


def _save(d: dict):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1)
    os.replace(tmp, PATH)


def record_vet(name: str, score: int, hireable: bool, card_hash: str):
    with _lock:
        d = _load(); a = d.setdefault(name, {"vets": 0, "hireable": 0, "jobs": 0, "verified": 0, "failed": 0, "last_score": 0, "card_hashes": []})
        a["vets"] += 1; a["hireable"] += int(hireable); a["last_score"] = score; a["last_seen"] = time.time()
        if card_hash and card_hash not in a["card_hashes"]:
            a["card_hashes"].append(card_hash)  # a changing card is itself a signal
        _save(d)


def record_job(name: str, passed: bool):
    with _lock:
        d = _load(); a = d.setdefault(name, {"vets": 0, "hireable": 0, "jobs": 0, "verified": 0, "failed": 0, "last_score": 0, "card_hashes": []})
        a["jobs"] += 1; a["verified" if passed else "failed"] += 1
        _save(d)


def get(name: str) -> dict:
    return _load().get(name, {})


def all_cards() -> dict:
    return _load()
