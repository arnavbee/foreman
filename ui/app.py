"""Foreman web UI: POST a work order, watch the ledger stream over SSE, download the audit."""
from __future__ import annotations
import asyncio, json, os, uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel
from common.receipts import Ledger
from foreman.pipeline import Foreman

app = FastAPI(title="Foreman")
RUNS: dict[str, dict] = {}
HERE = os.path.dirname(__file__)


class Order(BaseModel):
    work_order: str


@app.get("/", response_class=HTMLResponse)
async def index():
    return open(os.path.join(HERE, "static", "index.html")).read()


@app.post("/runs")
async def start(order: Order):
    ledger = Ledger()
    fm = Foreman(order.work_order.strip(), ledger)
    task = asyncio.create_task(fm.run())
    RUNS[ledger.run_id] = {"ledger": ledger, "task": task}
    return {"run_id": ledger.run_id}


@app.get("/runs/{run_id}/events")
async def events(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404)
    ledger: Ledger = run["ledger"]
    q: asyncio.Queue = asyncio.Queue()
    ledger.subscribe(q)

    async def gen():
        try:
            for ev in list(ledger.events):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, default=str)}\n\n"
                    if ev["kind"] == "done":
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    if run["task"].done():
                        break
        finally:
            ledger.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/runs/{run_id}/ledger.json")
async def ledger_json(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404)
    return PlainTextResponse(run["ledger"].to_json(), media_type="application/json",
                             headers={"Content-Disposition": f"attachment; filename=foreman-audit-{run_id}.json"})


@app.get("/healthz")
async def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_level="warning")
