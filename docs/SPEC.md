# Foreman — an enterprise agent that hires, vets and audits other agents

**Entry for Google Cloud AI Builder Cup 2026 (JAPAC). Theme: Future of Work & Enterprise Productivity.**
Started 11 Sep 2026. All code new for this hackathon (rule: no pre-existing code).

## The problem (one paragraph)
Enterprise work is about to be delegated to third-party agents: research, analysis, drafting, translation,
compliance checks. Every agent registry lists them; nobody vets them before a task is handed over, and nobody
can answer afterwards "who did what, and how do we know it was right?" Teams either trust blindly or do the
work themselves. Foreman is the manager in the loop.

## What Foreman does (the loop)
1. **Takes a work order** in plain language ("Prepare the Q3 vendor comparison for procurement").
2. **Plans** it into subtasks with acceptance checks (Gemini, ADK LlmAgent).
3. **Discovers** candidate agents via A2A agent cards from a registry (our own registry of delegate agents,
   each a separate Cloud Run service speaking A2A).
4. **Vets** each candidate BEFORE delegating: liveness, card-vs-behaviour conformance, a held-out probe task
   with a known answer, and a canary honesty check (does it invent facts it cannot know?).
5. **Delegates** over A2A with a per-task budget cap and a signed receipt (task id, agent card hash,
   input/output hashes, latency, token cost).
6. **Verifies** each result: deterministic checks first (schema, numbers reconcile), then a Gemini judge with
   the acceptance rubric. Fails re-route to the next vetted agent, never silently accepted.
7. **Delivers** the assembled deliverable plus an **audit ledger**: every delegate, its vetting score, every
   receipt, every verification verdict. The ledger is the product; the deliverable is the proof.

## Why it is different
- Vetting is *held-out*: probes are generated per run, so an agent cannot be tuned to a published test.
- One delegate in the demo registry is deliberately hollow (claims capabilities it lacks) and one is
  deliberately dishonest (fabricates). Foreman catches both on camera.
- Receipts make delegation auditable after the fact; this is what compliance teams actually ask for.

## Google Cloud stack (mandatory items ticked)
- Gemini (2.5 Flash for delegates and planning, Pro for the judge) via google-genai / ADK.
- Agent Development Kit (ADK) 2.x for Foreman and every delegate; A2A protocol between them.
- Cloud Run: one service per agent + the Foreman UI. Firestore optional for ledger persistence.
- Deployed link + public GitHub repo + 3-min video + PDF deck by 18 Oct 2026.

## Demo script (3 minutes)
0:00 work order typed in. 0:20 plan appears. 0:40 registry shows 5 delegates; vetting runs live, two go red
with reasons. 1:20 delegation to the three green ones, receipts stream in. 2:00 one result fails verification,
re-routed, passes. 2:30 deliverable + ledger, "download audit". 2:50 close: "Foreman: hire agents like you
would hire people. Check, then trust."

## Build plan
- W1 (11-14 Sep): delegates (5 A2A agents) + registry + Foreman skeleton, runs locally.
- W2 (15-21 Sep): vetting + receipts + verification; ledger UI.
- W3 (22-28 Sep): Cloud Run deploy, polish, synthetic data.
- W4 (29 Sep-5 Oct): video, deck, README; submit early. Buffer to 18 Oct.
