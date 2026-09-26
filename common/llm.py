"""Model selection. Real Gemini when a key exists, FakeLlm when FOREMAN_FAKE_LLM=1.

Also the one place that talks to the model, so it is the one place that owns rate limiting
and transient-failure retries. That matters for correctness, not just uptime: Foreman scores
other agents on what they reply, so a 429 from our own quota must never be recorded as an
agent giving a wrong answer.
"""
from __future__ import annotations
import os, json, re, time, asyncio, random
from collections import deque
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.models.google_llm import Gemini

FAKE = os.getenv("FOREMAN_FAKE_LLM") == "1" or not (os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))
# 2.5-flash / 2.5-pro were retired for new API keys (404, "no longer available to new users") on 26 Sep 2026.
# Pro-class models 429 on the free tier, so the strong path also runs on Flash until billing is on.
# Free-tier quotas are per project PER MODEL per day, and on 26 Sep 2026 gemini-3.8-flash allowed
# only 20 requests a day -- less than one Foreman run. Each model has its own daily bucket, so the
# fast and strong paths sit on different models and fall through a chain when one is exhausted.
FLASH = os.getenv("FOREMAN_MODEL_FAST", "gemini-3.1-flash-lite")
PRO = os.getenv("FOREMAN_MODEL_STRONG", "gemini-3.6-flash")
FALLBACKS = [m.strip() for m in os.getenv(
    "FOREMAN_MODEL_FALLBACKS", "gemini-3.1-flash-lite,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.8-flash"
).split(",") if m.strip()]

# Free-tier Gemini allows 5 generate_content requests per minute per model. Foreman fans out
# (planner, probe generator, every delegate, the judge), so without a shared limiter it burns
# the minute's budget in the vetting stage and every later call 429s. Raise this once billing
# is on: FOREMAN_RPM=0 disables the limiter entirely.
RPM = int(os.getenv("FOREMAN_RPM", "5"))
RETRIES = int(os.getenv("FOREMAN_LLM_RETRIES", "4"))
_TRANSIENT = ("RESOURCE_EXHAUSTED", "429", "UNAVAILABLE", "503", "INTERNAL", "500", "DEADLINE_EXCEEDED")

_calls: deque[float] = deque()
_exhausted: set[str] = set()   # models whose daily free quota ran out in this process
_gate: asyncio.Lock | None = None


class TransientModelError(RuntimeError):
    """Our quota or Google's capacity failed, not the agent under test."""


def is_transient(e: BaseException) -> bool:
    blob = f"{type(e).__name__} {e}"
    return any(t in blob for t in _TRANSIENT)


def is_daily_quota(e: BaseException) -> bool:
    """A per-day quota is not worth waiting out; the only useful move is a different model."""
    return "PerDay" in str(e)


def next_model() -> str | None:
    """First model in the chain whose daily free quota has not run out in this process."""
    return next((m for m in FALLBACKS if m not in _exhausted), None)


_TRANSPORT_ECHO = re.compile(
    r"\b(?:429|500|503)\s+(?:RESOURCE_EXHAUSTED|UNAVAILABLE|INTERNAL)\b"
    r"|adk-docs/agents/models/google-gemini/#error-code",
)


def looks_like_transport_error(text: str) -> bool:
    """True when a remote agent handed back a raw model/transport error instead of an answer.

    A delegate that 429s can surface the provider's error text as its reply. That is our
    infrastructure failing, not the agent lying, so it must not be scored as a wrong answer.
    Deliberately narrow: it matches the provider's own status line, not the word "error".
    """
    return bool(text) and bool(_TRANSPORT_ECHO.search(text))


def _retry_after(msg: str) -> float | None:
    m = re.search(r"retry(?:Delay|.{0,12}in)\D{0,4}(\d+(?:\.\d+)?)\s*s", msg, re.I)
    return float(m.group(1)) if m else None


async def _throttle() -> None:
    """Token bucket over a rolling 60s window, shared by every caller in this process."""
    global _gate
    if RPM <= 0:
        return
    if _gate is None:
        _gate = asyncio.Lock()
    async with _gate:                      # held across the sleep on purpose: serialising
        while True:                        # waiters is what keeps us under the limit
            now = time.monotonic()
            while _calls and now - _calls[0] >= 60:
                _calls.popleft()
            if len(_calls) < RPM:
                _calls.append(now)
                return
            await asyncio.sleep(60 - (now - _calls[0]) + 0.2)


class RetryingGemini(Gemini):
    """Gemini with the shared rate limiter and transient-failure retries applied at the model.

    The retry has to live here, not only in ask(): a delegate runs in its own process behind A2A,
    and when its model 429s the ADK runner turns the exception into an ordinary text event. Foreman
    then receives "503 UNAVAILABLE ..." as if the agent had said it, and scores the agent down for
    our quota problem. Retrying at the model keeps that string from ever becoming an answer.
    """

    async def generate_content_async(self, llm_request, stream: bool = False):
        for attempt in range(RETRIES):
            await _throttle()
            produced = False
            try:
                async for resp in super().generate_content_async(llm_request, stream=stream):
                    produced = True
                    yield resp
                return
            except Exception as e:
                # Once output has been yielded a retry would duplicate it, so only retry a clean failure.
                if produced or not is_transient(e) or attempt == RETRIES - 1:
                    raise
                if is_daily_quota(e):
                    _exhausted.add(llm_request.model or self.model)
                    alt = next_model()
                    if not alt:
                        raise
                    llm_request.model = self.model = alt
                    continue
                wait = _retry_after(str(e)) or min(2.0 * 2 ** attempt, 30.0)
                await asyncio.sleep(wait + random.uniform(0, 0.5))


def model_for(role: str, strong: bool = False):
    if FAKE:
        from common.fake_llm import FakeLlm
        return FakeLlm(role=role)
    return RetryingGemini(model=PRO if strong else FLASH)


def make_agent(name: str, role: str, instruction: str, description: str = "", strong: bool = False) -> LlmAgent:
    return LlmAgent(name=name, model=model_for(role, strong), instruction=instruction, description=description or instruction[:120])


async def ask(agent, text: str, user_id: str = "foreman") -> tuple[str, int, int]:
    """Run an agent with rate limiting and transient-failure retries.

    Raises TransientModelError when the quota or the service is the problem, so callers can
    tell "infrastructure failed" apart from "the agent answered badly".
    """
    last: BaseException | None = None
    for attempt in range(RETRIES):
        await _throttle()
        try:
            return await _ask_once(agent, text, user_id)
        except Exception as e:
            if not is_transient(e):
                raise
            last = e
            if attempt == RETRIES - 1:
                break
            wait = _retry_after(str(e)) or min(2.0 * 2 ** attempt, 30.0)
            await asyncio.sleep(wait + random.uniform(0, 0.5))
    raise TransientModelError(str(last)[:300])


async def _ask_once(agent, text: str, user_id: str = "foreman") -> tuple[str, int, int]:
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
