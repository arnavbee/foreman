import json
from common.receipts import Ledger, Receipt
from common.signing import verify_chain
from common.llm import parse_json
from foreman.pipeline import Foreman


def test_ledger_chain_and_signatures_verify_and_break():
    lg = Ledger("t")
    lg.emit("run", work_order="x")
    r = Receipt(run_id="t", task_id="t1", agent_name="a", agent_url="http://x", card_hash="c", input_hash="i").close("out")
    lg.receipt(r)
    lg.emit("done", status="ok")
    d = json.loads(lg.to_json())
    assert verify_chain(d)["ok"]
    d["events"][1]["receipt"]["latency_ms"] = 999
    v = verify_chain(d)
    assert not v["ok"] and v["first_bad"] == 1


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('Sure:\n```json\n{"pass": true}\n```')["pass"] is True
    assert parse_json('{"a":1} trailing')["a"] == 1
    assert parse_json("no json here", {}) == {}


def test_deterministic_checks_catch_bad_totals_and_hollow_output():
    fm = Foreman("x")
    bad = "| Vendor | Unit | Volume/mo | 3-yr total |\n|---|---|---|---|\n| A | $12 | 1,000 | $430,000 |"
    assert any("reconcile" in p for p in fm.deterministic_checks({"skill": "analysis", "accept": ""}, bad))
    good = bad.replace("430,000", "432,000")
    assert fm.deterministic_checks({"skill": "analysis", "accept": ""}, good) == []
    assert fm.deterministic_checks({"skill": "research", "accept": ""}, "Done.")
    long = " ".join(["word"] * 400)
    assert fm.deterministic_checks({"skill": "drafting", "accept": "Under 350 words"}, long)
