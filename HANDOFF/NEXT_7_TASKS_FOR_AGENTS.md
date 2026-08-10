# NEXT 7 TASKS — CWC / POST-CSCA-07

These are sequential scientific gates. A downstream task is blocked if its parent gate fails. Every confirmatory experiment requires: experiment ID, preregistration committed before result observation, frozen seeds/data split, exact primary metric, nulls, failure predicate, checksum-bound artifacts, independent replication, and explicit non-promotion boundary.

## TASK 1 — CSCA-08A: Observational Identifying-Assumption Contract

Select exactly ONE primary identifying structure that can exist without new `do_env` interventions. Priority candidate: an **observed exogenous regime/group variable R** whose assignment mechanism is argued to be upstream of the target transition and not caused by the latent outcome/noise being identified.

Deliverables:
- formal SCM/DAG and structural equations;
- explicit assumptions A1..Ak (exogeneity, support/overlap, mechanism invariance/change pattern, no forbidden R<-U->Y path, measurement reliability);
- exact causal quantity claimed identifiable under those assumptions;
- theorem/derivation of the observational equivalence class with and without A1..Ak;
- one constructive counterexample per assumption showing what breaks when it is removed;
- `FAIL` if the chosen assumption only restates the desired causal conclusion.

No real-data causal promotion in this task.

## TASK 2 — CSCA-08B: Regime-Conditioned Identifiability Benchmark

Build a deterministic/reproducible SCM family in which pooled factual observations are intentionally non-identifying but regime-conditioned observations become identifying only when the frozen assumption contract is true.

Required families:
- true identified model;
- observationally equivalent wrong topology under pooled data;
- hidden-confounder alternative;
- regime-direct-effect violation;
- selection-bias violation;
- regime-label corruption;
- support/positivity failure;
- weak-information boundary.

Evaluator must not receive the generator graph. Preserve exact ground truth only for scoring.

## TASK 3 — CSCA-08C: Information/Compute Certificate

Generalize the CSCA-07 converse to the regime-conditioned channel.

For candidate model index M and factual trace D with observed regime R, compute/estimate a valid information rate such as

`R_M = liminf_n (1/n) D_KL(P_*^{D|R} || P_M^{D|R})`

under the declared model class, and bind it to the necessary decision cost

`Cost_min >= kl(power || alpha) / R_M`.

Requirements:
- distinguish a necessary converse from a sufficient test guarantee;
- `R_M=0 -> PASSIVELY_UNIDENTIFIABLE / infinite necessary cost`;
- pre-run compute veto when the frozen budget cannot reach the required information;
- wall-clock, sample count and structural/evaluation cost recorded separately.

## TASK 4 — CSCA-08D: Anytime-Valid Assumption/Falsification Instrument

Implement an anytime-valid sequential test/e-process or confidence-sequence family for the observable implications of the identifying assumptions and candidate model.

The instrument must return separate states:
- `MODEL_OBSERVABLE_LAW_REJECTED`;
- `IDENTIFYING_ASSUMPTION_VIOLATED`;
- `INSUFFICIENT_INFORMATION_BUDGET`;
- `OBSERVATIONALLY_EQUIVALENT`;
- `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`.

Never collapse assumption failure into model falsification. Control multiplicity over tested regimes/candidates and mutation-test every authority transition.

## TASK 5 — CSCA-08E: Confounding / Aleatoric / Structural Discrimination Attack

Construct a three-way adversarial matrix where the same large residual can arise from:
1. wrong structural topology;
2. latent confounding;
3. correctly specified structure with larger aleatoric noise.

Require distinct observable predictions under the chosen assumption set or formally declare them non-identifiable. Attack with:
- hidden common cause;
- heteroskedastic noise;
- heavy tails;
- nonstationary noise variance;
- confounder strength sweep;
- topology-edge strength sweep;
- regime misclassification.

Primary metric is correct epistemic state, not raw prediction accuracy. A test that always calls `STRUCTURAL_ERROR` must fail.

## TASK 6 — CSCA-08F: Real Factual-Trace Eligibility Audit

Audit existing nanochat / prose / code traces for an actually defensible identifying channel. Do NOT treat `PROSE` vs `CODE`, document ID, timestamp, shard, or prompt position as exogenous merely because the labels exist.

For every potential R/instrument/group:
- provenance;
- assignment mechanism;
- temporal order;
- possible common causes;
- support/overlap;
- contamination/leakage;
- whether assumptions are testable or only asserted.

If no real trace satisfies the frozen contract, final verdict is `REAL_TRACE_IDENTIFYING_CHANNEL_NOT_ESTABLISHED` and causal abstraction remains blocked. This is a valid success of the gate.

## TASK 7 — CSCA-08G: Independent Replication + Promotion Decision

Only if Tasks 1-6 survive, run fresh frozen PRIMARY and independent REPLICATION cohorts and issue one final machine verdict.

Promotion requirements:
- type-I error within frozen bound;
- non-degenerate power where the information converse says power is feasible;
- zero silent authority under observational equivalence;
- hidden-confounder and aleatoric nulls not misclassified as topology falsification beyond the frozen error budget;
- held-out regimes/topologies tested;
- assumption violations produce abstention/downgrade, not causal certainty;
- exact evidence hashes and clean Git ancestry;
- H5 human review states exactly what remains capable of killing the claim.

Allowed terminal states:
- `OBSERVATIONAL_CAUSAL_ABSTRACTION_QUALIFIED_NARROWED`;
- `PASSIVE_IDENTIFICATION_ASSUMPTION_NOT_SUPPORTED`;
- `REAL_TRACE_IDENTIFYING_CHANNEL_NOT_ESTABLISHED`;
- `INSUFFICIENT_INFORMATION_BUDGET`.

Even a PASS does NOT authorize active causal control. The next programme after a genuine PASS would be a shadow-only replay-governor comparison against `resolution_aware_debt`, RPE, recency, uniform and random under equal compute, with false consolidation as a primary safety metric.
