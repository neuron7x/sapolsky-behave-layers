# ACT-R&D-03 — Execution Report

**Execution status:** `COMPLETE_FAIL_CLOSED`  
**Scientific eval:** `FAIL`  
**Scientific verdict:** `UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE`  
**Current authority:** `RESEARCH_ONLY`  
**Target authority:** `SHADOW_INFERENCE_QUALIFIED` — **NOT REACHED**

## 1. Intent executed

ACT-R&D-03 asked whether the system can know when a learned counterfactual model is too uncertain or structurally unsupported to issue causal authority. The act was executed in the declared order through the confirmatory uncertainty/abstention qualification and mandatory null attacks. Descendant runtime-authority stages were stopped after the qualification gate failed.

## 2. P0 — execution hermeticity

Direct clean-tree execution debt was closed for the research-ops path. Optional packages absent in this environment (`rustbpe`, `pyarrow`, `hypothesis`; `tomli` replaced by stdlib `tomllib` where applicable) were isolated explicitly rather than silently treated as passing functionality. `pytest --collect-only` completed with 386 tests collected.

Two additional direct gate import-path defects discovered during final verification (`verdict_binding_gate.py`, `validate_evidence.py`) were repaired so they no longer depend on `PYTHONPATH=.`.

## 3. Frozen CSCA-02-UA protocol

The H4/preregistration and calibration policy were frozen before held-out confirmatory execution. Calibration used 32 frozen seeds across 7 calibration families (224 cases). The selected policy was frozen under SHA-256:

`459a5ab08c34dd25931b969ebe9351917beb9d066943a31cc4284caf025d13c9`

The confirmatory PRIMARY and INDEPENDENT_REPLICATION cohorts each used 32 fresh frozen seeds across 7 held-out structural families (224 cases/cohort). Calibration + the two confirmatory cohorts therefore contain 672 main cases and 15,482,880 recorded structural-evaluation proxy units. Recorded wall time for those three main passes was approximately 58.07 seconds in this execution environment. These are execution measurements, not hardware-performance claims.

## 4. Confirmatory result

### PRIMARY

- accepted: 43 / 224;
- coverage: 0.19196428571428573;
- selective false causal authority: 0.0;
- no-abstention false causal authority: 0.42857142857142855;
- causal-rank accuracy given accept: 1.0;
- failure predicate: `COVERAGE_LT_0_20`.

The preregistered coverage floor required `>= 0.20`. The threshold was not changed after observing the result.

### INDEPENDENT_REPLICATION

- accepted: 45 / 224;
- coverage: 0.20089285714285715;
- selective false causal authority: 0.0;
- no-abstention false causal authority: 0.42857142857142855;
- causal-rank accuracy given accept: 1.0;
- cohort gate: PASS.

Replication success cannot overwrite PRIMARY failure because the preregistration required the conjunction of both cohorts.

## 5. Structural misspecification attacks

The frozen policy successfully rejected/abstained on zero-cause, common wrong-structure, latent-confounder-shift and insufficient-intervention-support attacks. A deliberately constructed case with good factual fit but wrong counterfactual structure also abstained: factual RMSE 0.1391582860, model disagreement only 0.0033958932, but intervention NRMSE 2.404179022. This demonstrates why factual predictive fit and same-family ensemble agreement are insufficient evidence of causal adequacy.

However the mandatory context-conditional attack failed. Twelve accepted `M10_CONTEXT_DEPENDENT_CAUSALITY` cases had `context_stability = 0.5`: six in PRIMARY and six in replication. The frozen policy could therefore issue one global causal candidate even where the preferred causal candidate changes across context strata.

Null-suite verdict: `NULL_ATTACK_EXPOSED_UNRESOLVED_FAILURE`.

## 6. Scientific interpretation

The experiment supports a narrow safety observation: abstention reduced measured accepted false authority from 96/224 under no abstention to 0/224 in each frozen confirmatory cohort while retaining some non-zero coverage. It does **not** qualify the mechanism because:

1. PRIMARY missed the frozen non-degenerate-coverage gate (43 accepts; at least 45 were required for 224 cases);
2. the mandatory context-conditional null exposed a missing representation of context-specific causal authority.

Therefore the system does not yet have sufficient epistemic authority to promote counterfactual credit into shadow inference.

## 7. Runtime consequence

The following stages were deliberately **not executed as scientific qualification**:

- real-model shadow inference;
- real-model replay control;
- physical inference/energy/latency qualification;
- active causal control;
- logit, token-sampling or weight modification.

The shadow observer/replay-governor substrate exists only as isolated tested code. It has no promotion authority.

`19_PHYSICAL_COMPUTE_REPORT.json` contains null measurements and explicitly records `NOT_EXECUTED_ANCESTOR_GATE_FAILED`.

## 8. Failure memory

The failed mechanism is retained as `RUIN-CSCA-02-UA-GLOBAL-UNCERTAINTY-AUTHORITY`. The existing 20% held-out coverage gate may not be weakened or re-tuned on these data.

The next admissible mechanism is **context-conditional causal authority**. It requires a new preregistration, new calibration data, new held-out seeds and a decision rule that represents conditional causal candidates rather than one globally privileged candidate.

## 9. Verification

Completed:

- `RD03-GATE`: PASS as an evidence-preservation gate;
- RD03 semantic mutation self-test: 4/4 corruptions detected;
- research-ops/research-execution/research-ingestion gates: PASS;
- causal-debt/VIA/architecture/hermeticity/complexity/inference-integrity gates: PASS;
- documentation gate: 51 claims / 51 hypotheses / 0 orphans;
- verdict-binding: 49 bound claims + 2 `NOT_TESTED`, PASS;
- evidence validation: PASS;
- focused research/VIA/causal-debt suite: 88 PASS / 0 FAIL;
- test collection: 386 tests collected.

A full non-mutation test execution was attempted with a 300-second cap but did not complete. No full-suite PASS is claimed from that attempt.

## 10. Final decision

`ACT-R&D-03` execution is complete, but the requested scientific promotion target failed.

**Evidence engineering:** PASS.  
**Scientific qualification:** FAIL.  
**Inference authority:** RESEARCH_ONLY.  
**Next hard gate:** newly preregistered context-conditional causal authority; no post-hoc rescue of CSCA-02-UA.
