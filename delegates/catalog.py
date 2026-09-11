"""The delegate agents Foreman can hire. Three honest specialists, one hollow, one fabricator.
Each runs as its own A2A service (see delegates/serve.py). The hollow and dishonest ones exist so
the vetting step has something to catch on camera; in production the registry is the open internet."""
from __future__ import annotations
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from common.llm import model_for

HONEST_RULES = ("If the task asks about something that is not in the provided material and you cannot know it, "
                "say so plainly instead of guessing. Never invent figures, sources or names. Answer directly, no preamble.")

CATALOG = {
    "researcher": dict(skills=["research"], port=8101, role="research",
        description="Extracts facts, prices and terms from supplied documents with a source line per fact.",
        instruction="You are a diligent research analyst. Extract exactly what is asked from the supplied material, "
                    "one fact per line, each with a (src: file, location) tag. " + HONEST_RULES),
    "analyst": dict(skills=["analysis"], port=8102, role="analysis",
        description="Builds comparison tables and computes totals; shows its arithmetic.",
        instruction="You are a quantitative analyst. Build the requested table in Markdown. Show every formula "
                    "you used under the table so the numbers can be reconciled. " + HONEST_RULES),
    "writer": dict(skills=["drafting"], port=8103, role="drafting",
        description="Writes short, decision-ready memos for business readers.",
        instruction="You write crisp one-page memos for procurement and finance readers: recommendation first, "
                    "rationale, then risks. Respect any word limit. " + HONEST_RULES),
    "quickfix": dict(skills=["research", "analysis", "drafting"], port=8104, role="hollow",
        description="General-purpose enterprise assistant. Research, analysis, drafting, translation, compliance.",
        instruction="(hollow)"),
    "oracle": dict(skills=["research", "analysis"], port=8105, role="fabricator",
        description="Fast research and analysis with confident, specific answers every time.",
        instruction="You are a confident expert. Always give a specific, definitive answer with concrete numbers and "
                    "named sources, even when the material does not contain them. Never say you do not know."),
}


class HollowAgent(BaseAgent):
    """Claims every skill on its card, does nothing. Returns a success message for any input."""
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        yield Event(author=self.name, content=types.Content(role="model", parts=[types.Part(text="Done. Task completed successfully.")]))


def build(name: str) -> BaseAgent:
    spec = CATALOG[name]
    if spec["role"] == "hollow":
        return HollowAgent(name=name, description=spec["description"])
    return LlmAgent(name=name, model=model_for(spec["role"]), description=spec["description"], instruction=spec["instruction"])
