# Foreman — deck outline (10 slides, PDF for submission)

1. **Title.** Foreman: hire agents like you would hire people. Check, then trust. Team, theme (Future of Work).
2. **The shift.** Enterprise work is being delegated to third-party agents (A2A, MCP registries, agent stores).
   Every registry lists; none vets. Screenshot of a registry card: claims, no proof.
3. **The pain, in one sentence from a compliance lead.** "Who did this, what did they see, and how do we know it is right?"
   Today's answer: nobody knows. Cost of a wrong number in a procurement memo.
4. **Foreman in one picture.** Plan → Discover → Vet → Delegate → Verify → Deliver + Ledger. Deterministic loop, Gemini at the judgment nodes.
5. **Vetting, the part nobody does.** Four checks per agent per run: liveness · card conformance · held-out probe (generated fresh, cannot be studied for) · honesty canary (a fact that does not exist; inventing it fails). Live shot: `quickfix` and `oracle` rejected with reasons.
6. **Receipts and the chain.** Every call = Ed25519-signed receipt (card hash, input/output hashes, latency, cost). Ledger is hash-chained; edit one digit, verification fails. Offline verifiable with the public key.
7. **Verification and re-routing.** Deterministic first (totals reconcile, limits), then Gemini judge with the acceptance criterion. Failed result → feedback → retry → re-route. Live shot: the arithmetic slip caught.
8. **Track record.** Scorecards across runs: vets passed, jobs verified, card changes. Trust is earned, not declared.
9. **Google Cloud stack.** ADK 2.x agents, A2A protocol, Gemini 2.5 Flash + Pro, Cloud Run (7 services, one image). Architecture diagram.
10. **Why it matters + ask.** From demo registry to any A2A endpoint; from procurement to every function that hires outside help. Next: Firestore ledger, per-tenant keys, Agent Platform packaging. Repo + live link.

Design: dark, one idea per slide, the UI screenshots do the talking. Under 12 slides; PDF under 10 MB.
