# DGC Product Qualification — Execution Runbook v1

Date: 2026-08-23
Status: `EXECUTABLE_FRONTIER / EXTERNAL_EVIDENCE_REQUIRED`

This runbook starts from the current canonical research/evidence architecture. It does not authorize skipping any gate or replacing missing external observations with synthetic evidence.

## 0. Verify upstream source authority

```bash
PYTHONPATH=. python scripts/dgc_product_external_source_gate.py
```

Required before materialization:

- `SWE_BENCH_VERIFIED = SOURCE_VERIFIED`;
- `TERMINAL_BENCH_2_1 = SOURCE_VERIFIED`;
- `MATERIALIZED_VERIFIED = 0` until local bytes/trees are checked;
- `EXECUTED = 0` until a bound confirmatory population completes.

`SOURCE_VERIFIED` is not materialization or execution.

## 1. Materialize both external workloads

Install the dedicated materialization environment:

```bash
python -m pip install -r dgc-external-requirements.txt
```

Materialize into a fresh evidence generation:

```bash
PYTHONPATH=. python scripts/dgc_materialize_external_sources.py \
  --output-root artifacts/dgc-materialized/gen-2026-08-23
```

The command emits `MATERIALIZATION_RECEIPT.json` only after both families pass byte/Git identity checks. Receipt fields keep `execution_authorized=false` and `product_promotion_authorized=false`.

### SWE-bench Verified

Frozen revision:

`03e151cf5560b1af6a4363c6a9d766deaaea6b56`

Frozen parquet SHA-256:

`bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`

Expected: `500` unique `instance_id` values.

Any hash/count/uniqueness mismatch => STOP and create a new evidence/preregistration generation.

### Terminal-Bench 2.1

Frozen commit:

`7131e4375048a0e408a8fb404b5f499d726b695b`

Repository tree:

`ddbd9031e59804a04e24019fc408d51b56a4e773`

Task tree:

`2f0f5fdc68f0befd9b4745386eb8698264b00d8a`

Dataset manifest blob:

`6e7e030fd37a7cefdbd597badcf8560c8748d995`

Expected: `89` tasks with upstream per-task SHA-256 digests.

Any Git-object or manifest mismatch => STOP.

## 2. Freeze content-addressed execution manifests

For each workload family produce SHA-256 content identities for:

- materialization receipt and task manifest;
- scorer/evaluator source;
- environment/container images;
- model IDs/versions and model manifest;
- prompt/system policy;
- tools;
- maximum per-task budget;
- provider pricing snapshot;
- DGC governance policy;
- product statistical plan.

Semantic labels such as `model-v1` are not evidence identities. `FrozenEvaluationHarness` requires lowercase SHA-256 manifests.

## 3. Fit B2 on calibration tasks only

B0/B1/B3 are static policy contracts. B2 is a learned cost-quality router and must be fitted only after the task split is frozen.

Prepare `DGC_B2_FIT_INPUT_V1` containing:

- frozen `LearnedRouterConfig`;
- complete calibration `task × action` counterfactual table;
- explicit forbidden/confirmatory task IDs;
- expected feature-schema SHA-256;
- expected training-algorithm SHA-256.

Run:

```bash
PYTHONPATH=. python scripts/dgc_fit_b2_baseline.py \
  --input artifacts/dgc-calibration/B2_FIT_INPUT.json \
  --output artifacts/dgc-calibration/B2_FIT_RECEIPT.json
```

The receipt binds:

- calibration input digest;
- forbidden confirmatory-task manifest digest;
- feature-schema digest;
- training-algorithm digest;
- calibration-task digest;
- fitted-model digest;
- fitted coefficients.

The receipt explicitly keeps `confirmatory_execution_authorized=false`.

Bind the verified receipt into `BaselinePanelSeal`. If B2 is not `executable_frozen`, P3 fails.

The exact CCF oracle is outside B0-B3 and never replaces a real baseline.

## 4. Estimate calibration-only variance components

Repeated stochastic runs are nested inside tasks; they are not independent task draws.

For every preregistered comparison/endpoint collect a balanced calibration-only table:

`comparison_id × task_id × replicate -> value`.

Hard requirements:

- at least 2 calibration tasks;
- at least 2 repeats/task;
- unique task/replicate rows;
- contiguous replicate IDs `0..R-1`;
- identical balanced replicate design across comparisons.

`calibration_variance.py` estimates:

`Var(mean) = sigma_between^2/N_tasks + sigma_within^2/(N_tasks*R)`.

## 5. Freeze cluster-aware repeated-trial count

Prepare `DGC_CLUSTER_AWARE_TRIAL_SIZING_INPUT_V1` with calibration observations, effects of interest and confirmatory task count.

```bash
PYTHONPATH=. python scripts/dgc_freeze_trial_sizing.py \
  --input artifacts/dgc-calibration/TRIAL_SIZING_INPUT.json \
  --output artifacts/dgc-calibration/TRIAL_SIZING_RECEIPT.json
```

The V2 product plan retains:

- global familywise alpha `0.05`;
- 2 families × 4 baselines × 3 endpoints;
- target power `0.90`;
- min 5 / max 50 trials/task;
- calibration-only variance estimation.

The receipt takes the maximum required repeats across preregistered comparisons.

If the between-task variance floor alone exceeds the target standard error, STOP with:

`UNDERPOWERED_TASK_HETEROGENEITY`.

No number of within-task repeats may be used to hide insufficient task diversity.

If required repeats exceed 50, STOP with `UNDERPOWERED`. Do not change alpha, margins or effects after seeing confirmatory outcomes.

## 6. Freeze one ConfirmatoryGenerationRoot per family

Before any confirmatory outcome is inspected, mint one immutable root with `freeze_confirmatory_generation`.

The root must simultaneously bind:

- exact repo commit and Git tree;
- `MATERIALIZED_VERIFIED` source authority;
- materialized workload tree/task manifest;
- executable-frozen B0-B3 panel including fitted B2;
- statistical-plan digest;
- trial-sizing receipt/repeat count;
- one common comparison-frame digest;
- exact policy -> governance-policy -> full-harness bindings;
- distributed task/policy/repeat population;
- distributed-evaluation spec digest.

Any cross-layer mismatch => STOP. A valid component from another generation cannot be substituted.

## 7. Execute the full distributed paired population

Run every confirmatory task under every preregistered policy with the frozen repeat count.

The distributed coordinator must enforce:

- deterministic `task × policy × replicate` identity;
- bounded leases and retries;
- cost reservation before dispatch;
- stale/forged/expired lease rejection;
- idempotent identical result commit;
- quarantine of conflicting duplicate evidence;
- full frozen population coverage;
- hash-chained audit log.

Every trial must emit:

- unique trial/work-unit identity;
- accepted-success outcome;
- normalized quality;
- catastrophic regret;
- complete physical cost certificate including human/infra/retry/failure loss where applicable;
- coverage/abstention state;
- raw provider/tool usage identifiers;
- evidence digest bound to the frozen harness.

Missing telemetry => invalid trial, never zero cost.

## 8. Certify completion and promote source authority to EXECUTED

`certify_confirmatory_completion` accepts only the exact generation/distributed spec and full work population.

Then `promote_executed_from_confirmatory` may promote the workload authority:

`MATERIALIZED_VERIFIED -> EXECUTED`

using the resulting `execution_population_digest`.

Manual `EXECUTED=true` is not authorized.

## 9. Run P9 simultaneous gate + CCF audit

For each family, require against **every B0-B3 baseline** on the same paired population:

- cost lower bound > 0;
- quality lower bound >= `-0.02`;
- catastrophic-regret lower bound >= `-0.01`;
- full matched coverage;
- identical paired population digest.

Any baseline failure => no primary real-workload product claim.

On the same frozen option population also report CCF:

- value regret relative to exact available-option allocation optimum;
- minimum cost to match/exceed DGC value without worse declared latency/risk;
- avoidable DGC cost.

CCF is an offline audit upper bound over observed options, not a production policy.

## 10. Evaluate commercial economics separately

Only after P9 passes compute CPS and full-cost net saving.

`NetSaving >= 0.30` is a commercial target, not a scientific theorem.

Never infer it from token reduction or synthetic runs.

## 11. Run G1-G5 no-retuning generalization

Freeze DGC and run without policy retuning:

- G1 unseen tasks;
- G2 unseen domain;
- G3 unseen model/provider;
- G4 changed pricing/latency/economic constraints;
- G5 perturbation/countermodel shift.

Every axis must preserve quality/regret/coverage gates and positive cost-effect direction. Retuning creates a new evidence generation.

## 12. Independent replication / formal review

Provide the exact hash-bound package to an independent party. Self-replay does not count.

The independent result must bind to the same package digest, methodology and preregistered bounds.

For critical mathematical propositions, independent theorem review or selected proof-assistant authority remains a separate obligation.

## 13. Seal P19 and promote only through machine gates

Populate the evidence bundle with real results, then generate `SHA256SUMS` and run:

```bash
PYTHONPATH=. python scripts/dgc_product_bundle_gate.py
PYTHONPATH=. python scripts/dgc_product_promotion_gate.py --require-stage PRODUCT_QUALIFIED
PYTHONPATH=. python scripts/dgc_release_repro_gate.py
```

Only after all PASS may a `dgc-product-*` release tag be created.

## 14. Production authority remains separate

After `PRODUCT_QUALIFIED`:

1. shadow mode with DGC control authority = false;
2. preregistered shadow qualification;
3. continuous assurance across functionality/operations/human/security/compliance/large-scale-impact evidence;
4. bounded canary <=10% traffic with hard spend/tool/step/time/concurrency caps and automatic rollback;
5. only then consider broader production control.

## Current immediate blockers

1. External workload binary/Git materialization has not completed in the current sandbox; source identity is verified, materialization is not.
2. No valid live provider confirmatory population has been executed in this environment.
3. B2 has no external calibration fit receipt yet.
4. Calibration-only between/within-task variance components and final repeat count are not yet measured externally.
5. No external ConfirmatoryGenerationRoot has been minted.
6. GitHub Actions continues to terminate before repository steps in the current environment; classify this as `CI_EXECUTION_UNAVAILABLE`.
7. Independent replication/review and real multi-node/cloud operational evidence are absent.

None of these blockers may be replaced with synthetic traces, manually promoted status fields or prose claims.
