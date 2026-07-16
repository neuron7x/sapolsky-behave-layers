# CWC Stanford-Grade Checklist — Status Audit

Machine-readable: `CHECKLIST_STATUS.json`. Audited at HEAD `a5df831`+.

## The four fundamental defects (critical summary) — all addressed locally
| # | Defect | Status | Evidence |
|---|---|---|---|
| 1 | Controller trained on privileged counterfactual target | **ADDRESSED** | R3-C without it → collapses (`artifacts/wp2-routing-v3-r3c/`); claim narrowed |
| 2 | Test capacity derived from task labels | **FIXED** | R3-C uses fixed pre-eval budget, label-free |
| 3 | No physical compute saving (both paths run) | **FIXED** | `forward_sparse` + 5 tests (compute scales with K, gradient isolation) |
| 4 | Surface shortcuts (format classifiable) | **CONFIRMED + FIXED** | leakage audit AUROC 1.0 = invalid; `surface_matched_task` → probes ~0.5 |

## Gate status
| Gate | Status | Note |
|---|---|---|
| G0 artifact integrity | PARTIAL | clean-release, RELEASE_MANIFEST, CITATION, claim_registry done; run make-release on release branch |
| G1 software verification | PARTIAL | ruff/mypy/65 tests/containers/CI-6-suites done; container build + CI matrix need infra (GitHub suspended) |
| G2 measurement validation | PARTIAL | physical dispatch + profiler cross-check done; latency/VRAM/reference-kernel remain; energy NOT_MEASURED |
| G3 benchmark identifiability | PASS (caveat) | oracle gap 99.8%; leakage confirmed + matched task built; 3rd mechanism family remains |
| G4 routing causality | PARTIAL | R-A/B/C separated; **R-C (autonomous) collapses** → SUPPORTED result is R-B only; better credit-assignment remains |
| G5 statistical validity | PARTIAL | 8 seeds + bootstrap; independent corpora + power analysis remain |
| G6 strong baselines | NOT_TESTED | MoD/MoE/recursive → **cloud-blocked** |
| G7 generalization | NOT_TESTED | real workloads / multi-scale → **cloud-blocked** |
| G8 Pareto + replication | NOT_TESTED | Pareto → cloud; replication → needs independent operator (not self-certifiable) |

## Priority progress
- **P0 (validity fixes): mostly done** — claim narrowed, NMI/AUROC fixed, physical dispatch, surface audit + matched task, CI complete, clean release, containers, claim registry, reproduce-primary. Remaining local: independent eval corpora.
- **P1 (routing proof): not started** — Routing v3 on 3 mechanism families + real workloads + MoD/MoE + Pareto → cloud.
- **P2 (cognitive mechanisms): partial** — plasticity core + oracle (NOT_IDENTIFIABLE unbudgeted; theory shows revival under cost budget); RCFR NOT_SUPPORTED; memory/structure not started.
- **P3 (full core): not started.**

## Honest bottom line
Every fundamental validity defect the review named is now addressed in the
codebase with tests. The measurement/identifiability/causality gates (G0–G5) are
PASS/PARTIAL. The gates that would establish a *general* architectural claim
(G6–G8: strong compute-matched baselines, real-workload generalization,
compute-equivalent Pareto, independent replication) are NOT_TESTED and require
cloud compute plus an independent operator — not achievable on this hardware.
The highest-value next step is unchanged and now unobstructed by validity leaks:
**Routing v3 at cloud scale** with all four fixes already in place.
