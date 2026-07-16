# CWC Remediation Act v2.0 — EXECUTION REPORT & HONEST MATURITY SCORE

Executed 2026-07-16 on branch `wp1-instrumentation`. This report scores CWC
under the Act's own rubric. **No score is claimed for a gate that did not
pass.** The purpose (Act §15) is to make future positive claims hard to fake —
so this report reports the true score, not the target.

> **UPDATE (A3.1, `artifacts/wp2-mechanism-v2_1/`):** the preregistered
> load-balance anti-collapse loss (lb=0.01) lifted **Stage A to 8/8 seeds →
> A3 ROUTING_CAUSALITY_SUPPORTED at claim tier** (learned = oracle, I_norm=1.0,
> perm-p=0.001 all seeds, force-incorrect 2078× worse, module-swap
> catastrophic). Stage B (inferred label) remains 6/8 → NOT_SUPPORTED. The
> adaptive-routing dimension rises 10→14 and the total to **57/100**. The
> routing-causality hard cap (59) is retained conservatively because full A3
> requires the inference regime (Stage B) too; it lifts to 86 once Stage B is
> reliable AND compute-equivalent Pareto (A7) is done.

## Package verdicts
| Pkg | Objective | Verdict | Evidence |
|---|---|---|---|
| A0 | Provenance closure | **PARTIAL** | run_manifest, make targets, 8 determinism/invariant tests; NOT all experiment code in scoped CI, no single-command full-repro CI |
| A1 | Measurement requalification | **PASS (energy excluded)** | overhead gate PASS (−0.46% median, CI upper +0.31%); energy INSTRUMENT_INVALID → energy claims prohibited |
| A2 | Mechanism-separable benchmark | **PASS** | oracle gap 99.9%, 48 pp, both stages; non-substitutability proven |
| A3 | Adaptive-routing causality | **NOT_SUPPORTED (reliability)** | causally perfect on 5–6/8 seeds (I_norm=1.0, interventions 2218× ratio), collapse on 2–3/8 → <80% consistency |
| A4 | Efficient RCFR | **BLOCKED** | behind A3; contract only (`docs/RCFR_FALSIFICATION_CONTRACT.md`) |
| A5 | RCFR causal validation | **NOT_TESTED** | blocked |
| A6 | Transfer / continual | **NOT_TESTED** | blocked |
| A7 | Compute-equivalent Pareto | **NOT_TESTED** | no MoE/MoD comparison |
| A8 | Independent replication | **NOT_POSSIBLE_BY_SELF** | requires a separate operator; cannot be self-certified |

## Deterministic maturity score (Act §2 rubric)
| Dimension | Max | Act-stated start | Now | Basis |
|---|---:|---:|---:|---|
| Reproducibility & provenance | 12 | 8 | 10 | manifest+checksums+make targets+determinism tests; −2: experiment code not in scoped CI, no one-command full-repro job |
| Measurement validity | 12 | 6 | 8 | overhead gate PASS; −4: no profiler-FLOP cross-check, energy INSTRUMENT_INVALID |
| Benchmark identifiability | 12 | 2 | 11 | A2 PASS decisively (oracle gap 99.9%, non-substitutable); −1: single task pair, one scale |
| Adaptive-routing causality | 18 | 3 | 10 | causality complete on majority seeds + all interventions; −8: fails ≥80% reliability, collapse basin |
| RCFR functional causality | 16 | 0 | 0 | blocked, contract only |
| Resource & Pareto validity | 14 | 4 | 5 | compute parity + overhead measured; −9: no Pareto vs MoE/MoD, energy excluded |
| Statistical validity | 10 | 7 | 9 | 8 seeds, paired bootstrap, MI+permutation, interventions, preregistered, per-seed retained; −1: reliability not modeled as a formal test |
| Generalization & replication | 6 | 0 | 0 | none |
| **TOTAL** | **100** | **30** | **53** | |

## Applicable hard caps (Act §2)
- Oracle-separation gate **PASSED** → the ≤49 cap does NOT apply.
- Routing-causality gate **NOT passed at claim tier** → **maximum score 59**.
- Score 53 is within [50, 59] and under the cap. Honest band:
  **"Component prototype with incomplete causality"** (50–69), at the lower
  edge because routing works but is not yet reliable.

**Reported score: 53/100** (up from 30), cap 59 until routing is reliable.
Reaching 87 requires: reliable A3 + RCFR causal validation (A5) + transfer
(A6) + compute-equivalent Pareto on ≥2 workloads (A7). Reaching 97 requires
independent replication (A8) — definitionally not self-certifiable.

## What was genuinely achieved (not inflated)
1. **First identifiable routing benchmark** — v1/v1.1's NULLs were proven to be
   benchmark artifacts (unidentifiable), not evidence that routing fails. A2's
   oracle gap of 99.9% establishes mechanism separation.
2. **First positive routing signal** — on the majority of seeds the learned
   controller achieves oracle-equivalent adaptive routing (I_norm=1.0), and
   every causal intervention confirms it (force-incorrect 2218× worse,
   module-swap catastrophic, permute destroys the gain).
3. **The remaining gap is named and localized** — bimodal optimization collapse
   (~25–37% of seeds), a known MoE failure with a standard fix (load-balancing
   / entropy regularization). This is the single next experiment.

## Prohibited-shortcut compliance (Act §14)
No thresholds changed post-hoc (all preregistered); coverage not counted as
science; oracle gap measured before routing claims; not claiming routing from
beating random alone; RCFR not claimed from LoRA; no TDP energy; controller
cost counted; no best-seed selection (all 8 reported, collapse included);
failed seeds NOT averaged away (reported as bimodal); negative/partial evidence
preserved, not overwritten.

## Machine-readable
```text
A0: PARTIAL
A1: PASS_ENERGY_EXCLUDED
A2_ORACLE_SEPARATION: PASS
A3_ROUTING_CAUSALITY: NOT_SUPPORTED_RELIABILITY (causal on 5-6/8 seeds)
A4_RCFR: BLOCKED
A5_RCFR_CAUSAL: NOT_TESTED
A6_TRANSFER: NOT_TESTED
A7_PARETO: NOT_TESTED
A8_REPLICATION: NOT_SELF_CERTIFIABLE
MATURITY_SCORE: 53/100 (cap 59)
NEXT_ACTION: add load-balancing/entropy-reg anti-collapse loss, re-run A3 8 seeds; if >=80% converge, A3 passes and A4 (RCFR) unblocks
```
