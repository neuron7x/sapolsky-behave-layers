# Evidence Act v3.0 — EXECUTION REPORT & HONEST SCORE (this session)

Executed 2026-07-16, branch `wp1-instrumentation`. The v3.0 rubric is FULLER
than v2.0 — it scores the entire CWC programme (memory, structure, joint
control, Pareto), most of which is genuinely untested. So the score below is
NOT a regression; it is a more complete, honest accounting.

## Package verdicts (this session, on top of prior A–E work)
| Act | Objective | Verdict | Evidence |
|---|---|---|---|
| A | Preserve/close evidence | **DONE** | `artifacts/history/{wp1,wp2-routing-collapse}` claim boundaries + checksums |
| B (B1) | FLOP ledger | SUPPORTED | `wp2-routing-v2/src/compute.py`, tested |
| B (B2) | Profiler cross-check | **PARTIALLY_ESTIMATED** | e_F=3.9% (SDPA attention uncounted by profiler); renderer e_F=0.0 (positive control); torch build reports 2·MAC |
| B (B5) | Energy | **NOT_MEASURED** | INSTRUMENT_INVALID upstream |
| C | Identifiable benchmark | **PASS** | oracle gap 99.8% (routing); RCFR benchmark: no-role/static fail by construction |
| D | Routing causality | **SUPPORTED** | `wp2-routing-v2`: bal 1.0, NMI 1.0, AUROC 1.0, CRE 1813×, 8 seeds |
| E | Typed semantic integrity | **DONE** | parser/renderer/channel + Broca/Wernicke/conduction lesions |
| **F** | **RCFR functional reuse** | **RCFR_NOT_SUPPORTED** | works (one module = R fns, role-only change predictable) but ties DISeL-with-role → not novel in isolation |
| G–J | memory / structure / joint / Pareto | **NOT_TESTED** | sequential gates; G–J require cloud compute |

## Deterministic score (v3.0 rubric)
| Domain | Max | Now | Basis |
|---|---:|---:|---|
| Provenance & reproducibility | 10 | 9 | history freeze, checksums, manifests, prereg |
| Software correctness | 8 | 7 | ruff/mypy/tests (30+ experiment tests) |
| Measurement validity | 12 | 7 | overhead PASS; FLOP cross-check PARTIALLY_ESTIMATED; energy NOT_MEASURED |
| Benchmark identifiability | 10 | 9 | oracle gap 99.8% + RCFR-necessity by construction |
| Routing causality | 12 | 11 | SUPPORTED, full metric suite, 8 seeds |
| Functional reuse | 10 | 3 | clean decisive NEGATIVE (mechanism real, not novel) |
| Memory & adaptation | 8 | 0 | NOT_TESTED |
| Structural plasticity | 8 | 0 | NOT_TESTED |
| Joint-control ablation | 8 | 0 | NOT_TESTED |
| Pareto evidence | 8 | 0 | NOT_TESTED |
| Independent replication | 6 | 0 | not self-certifiable |
| **TOTAL** | **100** | **46** | |

## Hard caps
Gate F not SUPPORTED → **max 69**. Score 46 sits under the cap; the binding
frontier is now G–J (memory, structure, joint control, real-workload Pareto) —
none started, all requiring cloud scale.

## The honest scientific narrative (two claim-tier results)
1. **Adaptive compute routing is causally real and reproducible** (Gate D):
   a label-free controller routes simple inputs cheaply and complex inputs
   through a typed semantic path under a binding budget, matching the oracle,
   confirmed by every intervention and lesion.
2. **Role-conditioned functional reuse is real but NOT novel in isolation**
   (Gate F): it works and is causally verified, but a fair prior-art baseline
   (input+role-gated rank bank) matches it exactly. RCFR's only surviving
   hypothesis is **integration** (Act I) — and that is not unblocked here,
   because §22 requires each mechanism to show independent value first.

Together these narrow the CWC claim honestly: the defensible, reproducible
result is routing causality; the individual "novel" mechanisms are prior art;
the open question — the only path to an undeniable architectural result — is
whether JOINT control yields a compute-equivalent Pareto advantage (Acts I–J)
against strong baselines (MoD, BUDDY, MoE, recursive), which requires cloud
compute and independent replication.

## Machine-readable
```text
ACT_A_FREEZE: DONE
ACT_B_METROLOGY: PASS_OVERHEAD / FLOPS_PARTIALLY_ESTIMATED / ENERGY_NOT_MEASURED
ACT_C_IDENTIFIABLE: PASS
ACT_D_ROUTING_CAUSALITY: SUPPORTED
ACT_E_SEMANTIC_INTEGRITY: DONE
ACT_F_RCFR: RCFR_NOT_SUPPORTED (not novel in isolation)
ACT_G_H_I_J: NOT_TESTED
SCORE: 46/100 (cap 69)
NEXT_DECISIVE: Act J compute-equivalent Pareto (candidate = supported routing) vs MoD/BUDDY/MoE/recursive on 2 real workloads, cloud scale, then independent replication
```
