# ACT-R&D-01 — Execution Report / Pass 1

Date: 2026-08-10

## Scope actually executed

This pass instantiated the ACT as a fail-closed research-ingestion subsystem and began the P0 reproduction queue. It does **not** claim corpus completion.

Created mandatory registry/report artifacts, immutable local extraction snapshots, atomic claims, contradiction records, executable hypotheses, reproduction queue, failure memory, and an automated ingestion gate. External source bytes could not be materialized from the execution container, so source-file SHA-256 fields remain explicitly `UNKNOWN_NOT_MATERIALIZED`; local extraction snapshot hashes are recorded separately.

## P0 / S01 — Counterfactual Shapley causal credit

### Narrow Skill/Luck conceptual reproduction

Verdict: `S01_SKILLLUCK_CONCEPT_REPRODUCED`.

A frozen two-step SCM reproduced the preregistered qualitative separation:

- identical observed return on Skill and Luck trajectories;
- terminal Skill action exact Shapley credit = `+0.375`;
- terminal Luck action exact Shapley credit = `0.0`;
- Shapley efficiency predicates passed.

Boundary: this is not reproduction of the S01 estimator, PPO/PTR training, or paper benchmark suite.

### OOD causal-credit qualifier

Verdict: `S01_OOD_CAUSAL_CREDIT_QUALIFIED`.

Authoritative run:

- 128 frozen seeds;
- 3 contexts;
- 256 independent trajectories/context/seed;
- 98,304 total trajectories;
- 7,962,624 exact counterfactual structural evaluations;
- maximum Shapley efficiency error `1.11e-16`.

`EXACT_CF_SHAPLEY` uniquely ranked the true delayed cause `A` first on 128/128 seeds in both OOD contexts and assigned zero normalized false-credit mass to the correlated non-cause and distractors.

The deliberately observational control showed why this matters:

- in `TRAIN_CONFOUNDED`, `OBS_ASSOC` ranked correlated non-cause `C` above true cause `A` (mean scores about `0.8795` vs `0.4372`);
- in `OOD_SIGN_FLIP`, it again ranked `C` above `A` (about `0.8129` vs `0.5440`);
- in `OOD_WEAK_CONFOUNDER`, observational association happened to rank `A` first.

Therefore association is context-sensitive while exact interventional credit remains invariant in this controlled SCM.

Boundary: exact Shapley is currently a synthetic **teacher/target**, not yet an operational replacement for `resolution_aware_debt()`. The next required S01 gate is matched-counterfactual-budget approximate estimation versus debt/RPE controls.

## P0 / S03 — controlled latent-dynamics transfer

Verdict: `S03_CONTROLLED_LATENT_DYNAMICS_NOT_QUALIFIED`.

The test was preregistered before execution. A capacity-matched 4-feature history-bearing ridge transition model was compared with a 4-feature stateless predictor on a partially observed second-order system, with an inadmissible future-observation model as leakage positive control.

OOD results:

- h=1: dynamic wins 64/64 seeds; mean MSE `0.394` vs stateless `8.026`;
- h=2: 64/64; `2.934` vs `25.655`;
- h=4: 64/64; `23.607` vs `76.099`;
- h=8: **54/64**, `166.825` vs `203.947`.

All horizon sign tests remained significant after Bonferroni correction, and mean h=8 error remained lower, but the frozen robustness gate required >=56/64 wins at h=8. It failed and was not weakened after seeing the result.

Interpretation: short/mid-horizon history state is useful in this controlled system, but that is insufficient evidence for robust long-horizon OOD rollout. The preregistered controlled S03 transfer hypothesis is killed in its current form.

## Promotion state

No external mechanism is promoted into CWC architecture.

- S01: narrow concept + exact synthetic OOD teacher qualified; full reproduction and matched-budget deployability remain open.
- S02: source/claim ingestion complete; controlled transfer remains blocked from real-model testing by missing local model/code/data substrate.
- S03: source ingestion complete; first controlled transfer test failed its frozen long-horizon robustness gate.
- S04: source/claim ingestion complete; reproduction not started in this pass.

## Next admissible work

1. S01 matched-budget approximate Counterfactual-Shapley estimator vs `resolution_aware_debt`, RPE, recency and equal-credit baselines.
2. S02 real-model semantic minimal-pair test only when an admissible local language-model representation is available; do not substitute hand-coded semantic labels and call it evidence.
3. S03 only retest after introducing a genuinely new preregistered state-transition/stabilization mechanism; do not relax 56/64 post hoc.
4. S04 controlled predicate-invention reimplementation after S01 P0 estimator gate or in a separate branch.

## Verification

Post-commit verification on the execution environment:

- `RESEARCH-INGESTION-GATE`: PASS;
- `RESEARCH-EXECUTION-GATE`: PASS;
- causal-debt gate: PASS;
- VIA gate: PASS with scientific ascension still blocked by prior evidence;
- architecture/hermeticity/complexity/inference-integrity: PASS;
- doc gate: PASS (`49 claims / 49 hypotheses / 0 orphans` in the existing central CWC registry);
- verdict binding: PASS (`47` sealed bindings + `2 NOT_TESTED`);
- evidence validation: PASS;
- focused ACT-R&D + causal-debt suite: `34 PASS`;
- broad environment-available suite with dependency-blocked modules and mutation meta-test excluded: `285 PASS / 23 SKIP`;
- full pytest collection: blocked by 7 modules requiring unavailable `rustbpe`, `tomli`, `hypothesis`, or `pyarrow`;
- mutation meta-test remains environment-blocked because it internally executes the missing-`hypothesis` property suite.

No full-suite PASS is claimed.
