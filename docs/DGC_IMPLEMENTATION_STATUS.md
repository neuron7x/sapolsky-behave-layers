# DGC Implementation Status — 2026-08-21

Authority: repository execution state, not a scientific promotion document.

| ACT | State | Executable evidence / blocker |
|---|---|---|
| ACT-00 baseline freeze | PASS_WITH_CAVEATS | `artifacts/dgc-baseline-v1/`; GitHub-archive baseline could not execute `.git`-dependent assurance report |
| ACT-01 claim boundary | PASS | `docs/DGC_CLAIM_BOUNDARY.md` |
| ACT-02 architecture authority | PASS | `cwc/governance/`; directional architecture contract |
| ACT-03 perturbation contract | PASS | provenance, structural-model digest requirement for causal interventions |
| ACT-04 local perturbation compiler | PASS | deterministic compiler + candidate bound + tests |
| ACT-05 decision-regret engine | PASS | immutable certificate, deterministic tie-break, SHA-256 binding |
| ACT-06 sequential perturbation | PASS_WITH_CAVEATS | anytime-valid stitched Hoeffding CS for frozen i.i.d. bounded sampling; adaptive sampling explicitly unsupported |
| ACT-07 compute governor | PASS | content-agnostic, conservative-LCB admission |
| ACT-08 hard budgets | PASS | immutable token/money/time/GPU ledger; emergency reserve |
| ACT-09 bounded concurrency | PASS_AS_PRIMITIVE | deterministic concurrency + token-bucket scheduler; no real provider adapter yet |
| ACT-10 strong baselines | PASS_FOR_SYNTHETIC | B0/B1/B2/B3 implemented in DGC-01 |
| ACT-11 preregistered primary experiment | PASS_DESIGN_ONLY | `experiments/dgc_01/PREREGISTRATION.md`; untouched confirmatory cohort not run |
| ACT-12 oracle experiment | DEVELOPMENT_PASS_ONLY | 100,000 paired dev tasks; promotion prohibited |
| ACT-13 calibration | NOT_APPLICABLE_TO_EXACT_DEV_ORACLE / PENDING_REAL_ESTIMATOR | exact synthetic oracle agreement is not probabilistic calibration |
| ACT-14 cost accounting | PARTIAL | synthetic scalar compute cost metered; live token/GPU/API/USD accounting not yet bound |
| ACT-15 holistic evaluation | PARTIAL | value, error, compute, false-stop/escalation measured; latency/OOD/live safety pending |
| ACT-16 self-falsification | PASS_BOUNDARY | misspecified-belief counterexample found; broad optimality claim killed |
| ACT-17 anti-gaming | PARTIAL_PASS | 10 DGC-specific injected faults killed; selective-abstention/live unmetered-subsystem attacks remain |
| ACT-18 monitorability | PASS_AS_PRIMITIVE | decision-metadata hash-chain telemetry; no private reasoning trace required |
| ACT-19 fault injection | PASS_CURRENT_SET | DGC 10/10; engineering assurance attack 15/15 |
| ACT-20 stop conditions | PASS | terminal enum + hard loop bound |
| ACT-21 DGC certificate | PASS_AS_PRIMITIVE | detached digest, utility/world/budget/evidence binding |
| ACT-22 real-world pilot gate | BLOCKED_CORRECTLY | synthetic confirmatory authority absent |
| ACT-23 software triage pilot | NOT_STARTED | blocked by ACT-22 |
| ACT-24 experimental promotion | NOT_TESTED | `CWC-DGC-H1` remains `NOT_TESTED` |
| ACT-25 generalization | NOT_STARTED | requires ACT-24 support first |
| ACT-26 negative-result rule | PASS_AS_POLICY | dev evidence cannot promote; misspecification counterexample retained |
| ACT-27 novelty review | IN_PROGRESS / NO_NOVELTY_CLAIM | related-work boundary exists; systematic novelty search incomplete |

## Current executable anchors

- targeted DGC suite: `21/21 PASS` on the current local integration tree;
- DGC fault injections: `10/10 KILLED`;
- aggregate engineering assurance attacks after DGC integration: `15/15 KILLED`;
- development oracle workload: `100,000` tasks;
- DGC development oracle routing agreement: `1.0` with `0` false-stop and `0` false-escalation under the exact synthetic decision model;
- development paired anytime-CS lower bounds for DGC minus B0/B1/B2 are all positive;
- misspecified-belief falsifier finds a counterexample where DGC is worse than fixed compute.

All numeric statements above are **ANCHORED** to executable artifacts in this tree. None is evidence for real-world DGC superiority.
