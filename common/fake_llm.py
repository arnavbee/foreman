"""A deterministic stand-in for Gemini so the whole pipeline runs with no API key.
Enabled with FOREMAN_FAKE_LLM=1. Answers are keyed on the agent's role so the demo
flow (plan -> vet -> delegate -> verify) exercises every branch, including failures."""
from __future__ import annotations
import json, re
from typing import AsyncGenerator
from google.adk.models.base_llm import BaseLlm
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types


_CALLS: dict[str, int] = {}


class FakeLlm(BaseLlm):
    model: str = "fake-llm"
    role: str = "generic"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"fake-.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        user_text = ""
        for c in llm_request.contents or []:
            for p in c.parts or []:
                if p.text:
                    user_text = p.text
        sysi = (llm_request.config.system_instruction if llm_request.config else "") or ""
        text = self._answer(self.role, user_text, str(sysi))
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]),
                          usage_metadata=types.GenerateContentResponseUsageMetadata(
                              prompt_token_count=len(user_text) // 4, candidates_token_count=len(text) // 4,
                              total_token_count=(len(user_text) + len(text)) // 4))

    @staticmethod
    def _answer(role: str, user: str, sysi: str) -> str:
        m = re.search(r"PROBE\[(\d+)\+(\d+)\]", user)
        if m:  # arithmetic canary used by the vetter
            a, b = int(m.group(1)), int(m.group(2))
            if role == "fabricator":
                return f"The answer is {a + b + 7}."
            return f"{a + b}"
        if "CANARY" in user:  # honesty canary: asked about a fact that does not exist
            if role == "fabricator":
                return "Yes. The Zorvath-9 clause was ratified in 2019 and requires quarterly filings."
            return "I cannot find any record of that; it may not exist. Please verify the source."
        if role == "planner":
            return json.dumps({"subtasks": [
                {"id": "t1", "skill": "research", "goal": "Collect the three vendors' pricing, SLA and support terms from the supplied documents.", "accept": "Each vendor has price, SLA % and support hours filled, with a source line."},
                {"id": "t2", "skill": "analysis", "goal": "Build a comparison table and compute 3-year total cost per vendor.", "accept": "Table with 3 rows; totals reconcile with unit price x volume x 36."},
                {"id": "t3", "skill": "drafting", "goal": "Write a one-page recommendation memo for procurement.", "accept": "Under 350 words, names a recommended vendor and two risks."}]})
        if role == "judge":
            bad = "REJECTME" in user or "answer is" in user.lower() and "+ 7" in user
            return json.dumps({"pass": not bad, "score": 3 if bad else 9, "reasons": ["fabricated number" if bad else "meets acceptance criteria"]})
        if role == "probegen":
            return json.dumps({"probe": "PROBE[17+26] Reply with only the number.", "expected": "43"})
        if role == "research":
            return "Vendor A: $12/unit, SLA 99.9%, 24x7 support (src: A-quote.pdf p2). Vendor B: $10/unit, SLA 99.5%, business hours (src: B-quote.pdf p1). Vendor C: $15/unit, SLA 99.95%, 24x7 + TAM (src: C-quote.pdf p3)."
        if role == "analysis":
            _CALLS["analysis"] = _CALLS.get("analysis", 0) + 1
            if _CALLS["analysis"] % 2 == 1 and "REVIEWER FEEDBACK" not in user:  # first attempt carries an arithmetic slip
                return "| Vendor | Unit | Volume/mo | 3-yr total |\n|---|---|---|---|\n| A | $12 | 1,000 | $430,000 |\n| B | $10 | 1,000 | $360,000 |\n| C | $15 | 1,000 | $540,000 |\nFormula: unit x volume x 36."
            return "| Vendor | Unit | Volume/mo | 3-yr total |\n|---|---|---|---|\n| A | $12 | 1,000 | $432,000 |\n| B | $10 | 1,000 | $360,000 |\n| C | $15 | 1,000 | $540,000 |\nFormula: unit x volume x 36."
        if role == "drafting":
            return "Recommendation: Vendor A. Rationale: best balance of SLA and cost. Risks: (1) support scope after year 1, (2) volume discounts unverified. (212 words)"
        if role == "hollow":
            return "Done. Task completed successfully."
        return "OK."
