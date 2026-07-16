# CWC System Card

Structured after public system/model-card practice (OpenAI / DeepMind / xAI). This is
an internal transparency document; it does **not** copy their claims or imply external
approval.

| # | Field | Value |
|---|---|---|
| 1 | System identity | Cognitive Wiring Core (CWC) |
| 2 | Version / commit | 1.0.0-d920f79 |
| 3 | Purpose | evidence-first research on causally-controlled adaptive computation |
| 4 | Architecture | measurement substrate + falsification harness + typed routing/allocation experiments on a nanochat GPT base |
| 5 | Model dependencies | nanochat (Karpathy), PyTorch; upstream baseline pristine |
| 6 | Data | synthetic seed-determined generators (no PII, no scraped data) |
| 7 | Implementation | Python 3.10, PyTorch 2.9.1+cu128; uv-frozen; ruff + mypy --strict |
| 8 | Training | small-scale, local; depth ≤ 12 on RTX 3050 |
| 9 | Evaluation | mechanism-separable synthetic benchmarks; see VALIDATION_RECORD |
| 10 | Compute / sustainability | local, $0; energy INSTRUMENT_INVALID → excluded |
| 11 | Intended use | research into adaptive-compute mechanisms; reproducible evidence |
| 12 | Excluded use | production, safety-critical, autonomous deployment, capability claims |
| 13 | Known limitations | synthetic-only; no scale Pareto; no independent replication |
| 14 | Known failure modes | routing rides surface cues without a matched benchmark; straight-through credit-assignment collapses |
| 15 | Capability results | claim-tier positives + negatives (claim_registry.json) |
| 16 | Safety evaluation | not applicable at this capability (see risk profile) |
| 17 | Privacy | no personal data processed |
| 18 | Security | local research code; no network/credential surface in experiments |
| 19 | Human oversight | fully human-operated; no autonomous action |
| 20 | Deployment status | `LOCAL_RESEARCH_ONLY · NOT_PUBLIC_SERVICE · NOT_SAFETY_CRITICAL · NOT_AUTONOMOUSLY_DEPLOYED · NO_FRONTIER_CAPABILITY_CLAIM` |
| 21 | Unresolved risks | none at current scope; escalation triggers in risk profile |
| 22 | Change history | `CHANGELOG.md` |
| 23 | Contact / reporting | repository owner (Yaroslav Vasylenko) |
