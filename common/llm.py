"""Model selection. Real Gemini when a key exists, FakeLlm when FOREMAN_FAKE_LLM=1."""
from __future__ import annotations
import os, json, re
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner

FAKE = os.getenv("FOREMAN_FAKE_LLM") == "1" or not (os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))
FLASH = os.getenv("FOREMAN_MODEL_FAST", "gemini-2.5-flash")
PRO = os.getenv("FOREMAN_MODEL_STRONG", "gemini-2.5-pro")


def model_for(role: str, strong: bool = False):
    if FAKE:
        from common.fake_llm import FakeLlm
        return FakeLlm(role=role)
    return PRO if strong else FLASH


def make_agent(name: str, role: str, instruction: str, description: str = "", strong: bool = False) -> LlmAgent:
    return LlmAgent(name=name, model=model_for(role, strong), instruction=instruction, description=description or instruction[:120])


async def ask(agent, text: str, user_id: str = "foreman") -> tuple[str, int, int]:
    """Run any ADK agent (local or RemoteA2aAgent) once and return (final_text, tokens_in, tokens_out)."""
    runner = InMemoryRunner(agent=agent, app_name=f"app_{agent.name}")
    session = await runner.session_service.create_session(app_name=f"app_{agent.name}", user_id=user_id)
    out, tin, tout = [], 0, 0
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    async for ev in runner.run_async(user_id=user_id, session_id=session.id, new_message=msg):
        um = getattr(ev, "usage_metadata", None)
        if um:
            tin += um.prompt_token_count or 0
            tout += um.candidates_token_count or 0
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.text and (ev.is_final_response() or getattr(ev, "partial", False) is False):
                    out.append(p.text)
    try:
        await runner.close()
    except Exception:
        pass
    # the last text part is the final answer; earlier ones are intermediate
    return (out[-1] if out else ""), tin, tout


def parse_json(text: str, default=None):
    """Tolerant JSON extraction from model text (handles ```json fences and prose)."""
    if not text:
        return default
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    cand = m.group(1) if m else None
    if not cand:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        cand = m.group(1) if m else None
    try:
        return json.loads(cand) if cand else default
    except Exception:
        return default
