# Integration Act v2.0 — EXECUTION REPORT & UPDATED MATURITY SCORE

Executed 2026-07-16, branch `wp1-instrumentation`. Reports the true score under
the CWC rubric — no score claimed for an unearned gate.

## Package verdicts
| §/Pkg | Objective | Verdict | Evidence |
|---|---|---|---|
| §1 | Freeze v1 + housekeeping | **DONE** | FINAL_CLAIM_BOUNDARY.json; runner_mixed ruff-clean; experiments in CI/Makefile |
| §3-5 | Typed semantic benchmark + 2 physical paths | **DONE** | DirectPath (local-w1, fails HARD) vs SemanticParser+Renderer |
| §9 | Oracle-gap identifiability | **PASS** | gain 0.998, HARD gap 41pp, oracle 1.0/1.0, 0 violations |
| §10 | Function isolation | **PASS** | parser ≥0.99, tuple 1.0, renderer ≥0.99, direct EASY 1.0 / HARD 0.004 |
| §11-12 | Routing causality | **SUPPORTED** | bal 1.0, NMI 1.0, AUROC 1.0, CRE 1813×, SL 873×, learned<random<shuffled, 8 seeds, 0 violations |
| §13 | Aphasia-analogue lesions | **PASS** | production (Broca) vs semantic (Wernicke/conduction) cleanly dissociated |
| §14 | Semantic feedback | **DONE** | deterministic output→tuple round-trip |
| §15 | Resource accounting | **PARTIAL** | parity + controller overhead <5%; no full Pareto vs MoE/MoD |
| A4-A8 | RCFR / transfer / Pareto / replication | **BLOCKED / NOT_TESTED** | RCFR unblocks now (§18) |

## Deterministic maturity score
| Dimension | Max | Prior | Now | Basis |
|---|---:|---:|---:|---|
| Reproducibility & provenance | 12 | 10 | 10 | manifest, checksums, make targets, 24 tests, determinism, prereg |
| Measurement validity | 12 | 8 | 8 | overhead PASS, parity, ctrl overhead <5%; energy INSTRUMENT_INVALID; no profiler cross-check |
| Benchmark identifiability | 12 | 11 | 12 | oracle gap 99.8% + isolation, typed mechanism-separable |
| Adaptive-routing causality | 18 | 14 | 17 | **full §12 pass, 8 seeds, all metrics + interventions + lesions**; −1 single task/scale |
| RCFR functional causality | 16 | 0 | 0 | correctly blocked (now unblocked to start) |
| Resource & Pareto validity | 14 | 5 | 6 | parity + overhead measured; no compute-equivalent Pareto vs MoE/MoD |
| Statistical validity | 10 | 9 | 9 | 8 seeds, paired bootstrap, NMI/AUROC/permutation, per-seed, prereg |
| Generalization & replication | 6 | 0 | 2 | compositional split (unseen test tuples); no 2nd hw/scale, no replication |
| **TOTAL** | **100** | **57** | **64** | |

## Applicable hard caps
- Oracle-separation gate **PASSED** → ≤49 cap lifted.
- **Routing-causality gate PASSED** → the ≤59 cap is LIFTED to **86**
  (compute-equivalent Pareto not yet done).
- Score **64/100** (up from 57), band "component prototype → supported
  component". The gate that mattered — routing causality — now passes at claim
  tier on a richer typed-semantic benchmark than the prior mechanism result.

**Path to 87:** compute-equivalent Pareto vs MoE/MoD/dynamic-depth (A7) +
RCFR causal validation (A5) + transfer (A6). **To 97:** independent replication
(A8) — not self-certifiable.

## What was genuinely achieved
1. **First full ROUTING_CAUSALITY_SUPPORTED in the CWC programme** — a
   label-free controller learned to route simple inputs cheaply and complex
   inputs through a typed semantic path under a binding capacity, matching the
   oracle, with every causal intervention and lesion confirming the mechanism.
2. **Meaning preservation is measured, not asserted** — the deterministic
   output→tuple round-trip and the lesion dissociations show the semantic path
   carries and can corrupt meaning in predictable, separable ways.
3. **The negatives are preserved** — v1/v1.1 (ROUTER_COLLAPSE) frozen with a
   claim-boundary file; the collapse was shown to be benchmark-unidentifiability
   and (in the mechanism study) optimization, not a routing-mechanism deficit.

## §14 prohibited-shortcut compliance
Thresholds preregistered; coverage not counted as science; oracle gap measured
before routing claims; not claiming routing from beating random alone (beats
random AND frozen AND shuffled, with NMI/AUROC/interventions); RCFR not claimed;
no TDP energy; controller cost counted; no best-seed selection (8/8 reported);
no averaging-away of failures (none occurred); negative evidence preserved.

## Machine-readable
```text
FREEZE_V1: DONE
BENCHMARK_IDENTIFIABLE: PASS
ISOLATION: PASS
ROUTING_CAUSALITY: SUPPORTED
LESION_SEPARABILITY: PASS
COMPUTE_PARITY: PASS
PARETO_EVIDENCE: NOT_TESTED
RCFR: UNBLOCKED_NOT_STARTED
MATURITY_SCORE: 64/100 (cap 86)
NEXT_ACTION: sequence-level RCFR with fixed low-rank primitive bank (coeffs only), then compute-equivalent Pareto vs MoE/MoD
```
