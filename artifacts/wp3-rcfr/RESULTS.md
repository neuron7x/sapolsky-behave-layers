# WP-3 RCFR — RESULTS (Act F). VERDICT: `RCFR_NOT_SUPPORTED`

8 seeds, preregistered (`../../experiments/wp3_rcfr/PREREGISTRATION.md`).
Data `raw_runs/`, stats `analysis.json`, verdict `verdict.json`.

## Verdict
Role-conditioned functional reuse **works but is not novel in isolation**: a
fair, strong input+role-gated rank baseline (DISeL-with-role) matches it exactly.
This confirms `docs/RCFR_FALSIFICATION_CONTRACT.md` at claim tier — conditional
low-rank modulation is prior art; RCFR's only possible value is INTEGRATION.

## Per-mode (mean over 8 seeds), accuracy on element-wise permutation ops
| Mode | acc (seen) | acc (unseen seq) | trainable params | reads |
|---|---:|---:|---:|---|
| shared_no_role | 0.238 | 0.237 | 8 768 | fixed linear W, role in input |
| static_lora | 0.230 | 0.231 | 8 776 | one fixed low-rank delta |
| fixed_role | 0.230 | 0.231 | 8 776 | ΔW at a constant role |
| **disel_gated** (strong baseline) | **1.000** | **1.000** | 17 544 | input+role-gated rank bank |
| separate_modules (capacity) | 1.000 | 1.000 | 41 536 | one W per role |
| **rcfr** (candidate) | **1.000** | **1.000** | 13 448 | role→coeffs→ΔW |

The LINEAR operator makes role-weight modulation **necessary**: shared_no_role,
static_lora and fixed_role all sit at chance (1/16 ≈ 0.0625 per token → ~0.23
sequence-level) — one fixed linear map cannot be R distinct permutations.

## F5 gate
| Criterion | Result |
|---|---|
| same module ≥2 functions (beats no-role & static) | **PASS** (rcfr 1.0 vs 0.23) |
| role-only changes function predictably | **PASS** (follows-wrong-role fn = 1.00; role permutation removes 98% of advantage) |
| transfers to unseen compositions | **PASS** (unseen 1.000) |
| **beats strongest conditional-adapter (DISeL)** | **FAIL** (rcfr − disel = 0.0, paired CI [0.0, 0.0]) |

Four criteria required; three pass, the decisive one fails → **RCFR_NOT_SUPPORTED**.

## Causal interventions (RCFR, mean over 8 seeds)
- forced wrong role → output follows the WRONG role's function (agreement 1.00):
  role-only change produces the predicted functional change — RCFR genuinely
  re-parameterizes one module by role.
- role permutation removes 98% of the advantage (≥80% required).
- module swap (corrupt ΔW) and random role collapse accuracy to chance.

These confirm the MECHANISM is real and causal — the module's function IS the
role-conditioned weight. But a prior-art input-gated rank bank achieves the
same, so the mechanism carries no novelty in isolation.

## Honest interpretation
This is a claim-tier NEGATIVE that sharpens the research claim, not a failure:
1. Adaptive routing is causally real and reproducible (Gate D, `wp2-routing-v2`).
2. Role-conditioned functional reuse is a real, causally-verified mechanism…
3. …but provides **no advantage over existing conditional adaptation in
   isolation** — exactly as the falsification contract predicted from prior art
   (HyperNetworks, HyperFormer, DISeL).
4. RCFR's only remaining hypothesis is **integration** (Act I joint control):
   whether role + route + depth + memory JOINTLY beat the best single-axis
   adaptive baseline. That is the next gate, and it is NOT unblocked by this
   result (F did not pass) — per §22 the joint claim requires each mechanism to
   first show independent value, which RCFR did not.

## Parameter note (not a preregistered criterion)
RCFR reaches 1.0 with 13 448 params vs DISeL's 17 544 and separate_modules'
41 536 — a marginal efficiency edge, but not the preregistered gate and not a
robust novelty claim on its own. Reported for completeness, not as support.

## Prohibited wording
"RCFR is a novel mechanism" — refuted in isolation. "RCFR beats adapters" — it
matches, does not beat. Only integration (Act I) could revive an RCFR claim.
