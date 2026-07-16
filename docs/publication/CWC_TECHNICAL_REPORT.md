# Cognitive Wiring Core: A Falsification-First Study of Causally-Controlled Adaptive Computation

**Status:** working technical report at commit `d920f79`+. Every number traces to a
committed evidence bundle; no result is claimed beyond its gate.

## Abstract
We ask whether *causally-controlled* adaptive computation can beat static computation at
equal budget. Rather than assert an architecture, we build a verified measurement
substrate and a falsification harness, and report what survives. We contribute: (1) an
**identifiability theorem** — the value of adaptive control is the context×choice
interaction `γ`, realized only under a binding budget; (2) an exact verification that
adaptive allocation beats best-static by **P(m>K)** (max error 0.0000, 8×4); (3) a
dissection of learned routing into **credit-assignment** and **route-decision cost**,
showing a leakage-free controller recovers oracle routing under a binding budget but
that on a surface-matched task **the route decision costs as much as the computation**;
and (4) a set of preserved negatives (functional reuse ties prior art; plasticity
non-identifiable unbudgeted; fractal emergence unsupported). We claim **no** scale Pareto
advantage and **no** independent replication.

## 1. Introduction
Adaptive computation promises to spend more compute on harder inputs. The open question
is whether an observed gain is *causal control* or an artifact of extra capacity or
optimization. CWC is built to answer this by falsification, not demonstration.

## 2. Research question
Can a learned controller route/allocate compute causally, without leakage, such that the
advantage is not explained by static architecture, capacity, or optimization — and does
it translate to a compute-equivalent advantage?

## 3. Related work
See `RELATED_WORK_AND_NOVELTY_REVIEW.md` (systematic search PENDING). Nearest: MoD,
MoE/Switch, DISeL/HyperFormer, EWC/SI/MAS.

## 4. Formal framework
Oracle gap `G = 𝔼_c[max_a(β_a+γ_{c,a})] − max_a β_a`. A weakly-dominant choice forces
`G=0`; identifiability is a **constrained** property (needs a binding budget). Realized
value discounts route-decision cost: `V_realized = G − c_route` (§8).

## 5. Methods
Measurement substrate (WP1): deterministic FLOP/VRAM/routing instrumentation, 207 tests,
99.46% branch coverage, 12/12 mutation kills. Mechanism-separable synthetic benchmarks
with a proven oracle gap and a surface-leakage audit. Controllers trained under three
regimes (oracle-supervised / value-distillation / end-to-end); only end-to-end licenses
an autonomous-routing claim.

## 6. Results
- **Identifiability (L1):** oracle gap 99.8%, LCB95>0 — a benchmark with a real
  adaptive-compute advantage exists.
- **Allocation (L2′):** adaptive allocation beats best-static by exactly `P(m>K)`, max
  error 0.0000 across 8 seeds × 4 regimes, beating input-blind random depth.
- **Routing credit-assignment (L2a):** the earlier straight-through end-to-end *collapse*
  was an estimator artifact; a REINFORCE controller (`L=L_task+λ·C_use`, no privileged
  target, label-free capacity) reaches AUROC 1.0 (learned 0.009 vs random 0.48, 8 seeds)
  — only at λ≥1 (binding budget).
- **Route-decision cost (L2b):** on a surface-matched benchmark (probes ~0.5), neither a
  cheap nor an attention controller routes above chance (AUROC ~0.51), even under direct
  supervision → the route decision costs ~the expensive computation.

## 7. Causal interventions
forced-correct ≈ oracle; forced-wrong degrades as predicted; route-shuffle removes the
advantage; frozen/reinit/constant controllers fail — establishing that the routing signal
is causal, within the stated (surface-caveated) scope.

## 8. Negative results (preserved)
RCFR ties DISeL-with-role (`RCFR_NOT_SUPPORTED`); metaplasticity benchmark
non-identifiable unbudgeted; fractal emergence unsupported. All frozen, checksummed.

## 9. Resource accounting
All results reproduce in seconds–minutes on CPU / RTX 3050; $0. Energy INSTRUMENT_INVALID
→ excluded. Cloud tiers for a scale claim: `EXPECTED_RUNTIME_HARDWARE_AND_COST.md`.

## 10. Limitations & claim boundary
Synthetic-only, small-scale, no scale Pareto, no independent replication (see
`LIMITATIONS_BROADER_IMPACTS_AND_ENVIRONMENT.md`, `claim_registry.json`).

## 11. Reproducibility
`make -f Makefile.cwc verify && make reproduce-primary`; per-result commands in
`RESULT_TO_SCRIPT_MATRIX.csv`.

## 12. Conclusion
CWC does not (yet) show an architecture that wins at scale. It shows, causally and
reproducibly, *where* adaptive-compute value comes from and *when it vanishes* — a
falsification-first foundation for the decisive cloud experiment.
