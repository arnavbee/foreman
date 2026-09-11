"""Serve one delegate as an A2A agent. `python -m delegates.serve researcher` -> http://localhost:8101
Cloud Run: PORT is injected; PUBLIC_URL is the service URL so the agent card advertises a reachable endpoint."""
from __future__ import annotations
import os, sys
import uvicorn
import warnings
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")
from google.protobuf.json_format import ParseDict
from a2a.types import AgentCard
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from delegates.catalog import CATALOG, build


def card_for(name: str, url: str) -> AgentCard:
    """The card is the agent's own claim about itself. Foreman treats it as a claim, not a fact."""
    spec = CATALOG[name]
    return ParseDict({
        "name": name, "description": spec["description"], "version": "0.1.0",
        "supportedInterfaces": [{"url": url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text/plain"], "defaultOutputModes": ["text/plain"],
        "skills": [{"id": sk, "name": sk, "description": f"{sk} for enterprise work orders", "tags": ["enterprise", sk]} for sk in spec["skills"]],
    }, AgentCard())


def app_for(name: str):
    spec = CATALOG[name]
    port = int(os.getenv("PORT", spec["port"]))
    public = os.getenv("PUBLIC_URL")  # e.g. https://researcher-xyz-uc.a.run.app
    url = public.rstrip("/") if public else f"http://localhost:{port}"
    return to_a2a(build(name), agent_card=card_for(name, url)), port


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DELEGATE", "researcher")
    app, port = app_for(name)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
