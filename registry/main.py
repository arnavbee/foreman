"""A minimal agent registry: knows delegate URLs, serves their A2A cards. In the real world this is
NANDA, an A2A directory or a vendor list; the point is that Foreman trusts NOTHING on the card until vetted."""
from __future__ import annotations
import os, asyncio, httpx
from fastapi import FastAPI

WELL_KNOWN = "/.well-known/agent-card.json"
DEFAULT = "researcher=http://localhost:8101,analyst=http://localhost:8102,writer=http://localhost:8103,quickfix=http://localhost:8104,oracle=http://localhost:8105"


def configured() -> dict[str, str]:
    out = {}
    for item in os.getenv("DELEGATE_URLS", DEFAULT).split(","):
        if "=" in item:
            n, u = item.split("=", 1)
            out[n.strip()] = u.strip().rstrip("/")
    return out


async def fetch_cards(urls: dict[str, str]) -> list[dict]:
    async def one(name, url):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(url + WELL_KNOWN)
                return {"name": name, "url": url, "alive": r.status_code == 200, "card": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return {"name": name, "url": url, "alive": False, "card": None, "error": str(e)[:120]}
    return await asyncio.gather(*(one(n, u) for n, u in urls.items()))


app = FastAPI(title="Foreman registry")


@app.get("/agents")
async def agents():
    return await fetch_cards(configured())


@app.get("/healthz")
async def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8100)), log_level="warning")
