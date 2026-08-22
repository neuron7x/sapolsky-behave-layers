# DGC Product Qualification — Execution Runbook v1

Date: 2026-08-23
Status: `EXECUTABLE_FRONTIER / EXTERNAL_EVIDENCE_REQUIRED`

This runbook starts from the current canonical research/evidence architecture. It does not authorize skipping any gate.

## 0. Verify upstream source authority

Run:

```bash
PYTHONPATH=. python scripts/dgc_product_external_source_gate.py
```

Required result before materialization:

- `SWE_BENCH_VERIFIED = SOURCE_VERIFIED`;
- `TERMINAL_BENCH_2_1 = SOURCE_VERIFIED`;
- `MATERIALIZED_VERIFIED = 0` until local bytes/trees are actually checked;
- `EXECUTED = 0` until benchmark trials actually run.

`SOURCE_VERIFIED` must never be interpreted as local materialization or execution.

## 1. Materialize external workloads

Install the dedicated, pinned materialization dependency set in the intended execution environment:

```bash
python -m pip install -r dgc-external-requirements.txt
```

Then materialize **both** frozen families into a fresh evidence generation:

```bash
PYTHONPATH=. python scripts/dgc_materialize_external_sources.py \
  --output-root artifacts/dgc-materialized/gen-2026-08-23
```

The command emits `MATERIALIZATION_RECEIPT.json` only after both families pass. The receipt explicitly keeps `execution_authorized=false` and `product_promotion_authorized=false`.

### SWE-bench Verified

Use frozen dataset revision:

`03e151cf5560b1af6a4363c6a9d766deaaea6b56`

Required primary parquet SHA-256:

`bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`

Expected rows: `500` unique `instance_id` values.

The materializer verifies the exact SHA-256 first, then uses pinned `pyarrow` to read only the `instance_id` column and generate a task-manifest digest. Any hash/count/uniqueness mismatch => STOP. Do not silently use another revision.

### Terminal-Bench 2.1

Use frozen commit:

`7131e4375048a0e408a8fb404b5f499d726b695b`

Repository tree:

`ddbd9031e59804a04e24019fc408d51b56a4e773`

Task tree:

`2f0f5fdc68f0befd9b4745386eb8698264b00d8a`

Dataset manifest blob:

`6e7e030fd37a7cefdbd597badcf8560c8748d995`

Expected tasks: `89` and every task must have its published SHA-256 digest.

The materializer performs a detached exact-commit Git fetch and verifies all four Git identities before sealing the task tree. Any mismatch => STOP.

## 2. Freeze execution manifests

For each family seal:

- materialization receipt + task manifest;
- scorer/evaluator source digest;
- environment/container image digest(s);
- model IDs/versions;
- prompt/system policy;
- tool definitions;
- maximum per-task budget;
- provider pricing snapshot;
- DGC policy digest;
- statistical-plan digest.

Run the workload sealing contract. Any missing task/environment/scorer identity => `harness_frozen=false`.

## 3. Freeze baseline panel

B0/B1/B3 static policy configs must have implementation and config digests.

For B2:

1. use calibration tasks only;
2. freeze feature schema and training algorithm before outcome-dependent fitting decisions;
3. fit B2;
4. record calibration-task digest and fitted-model digest;
5. seal `BaselinePanelSeal`.

If B2 is not executable-frozen, P3 fails.

The exact Counterfactual Compute Frontier (CCF) is an **audit oracle outside B0-B3**. It must be reported in addition to the real baselines and cannot replace them.

## 4. Freeze repeated-trial count

Use the deterministic 20/80 task split from `product_statistical_plan.py`.

Only calibration outcomes may estimate variance.

Compute repeated-trial count under:

- target power `0.90`;
- global familywise alpha `0.05`;
- 2 families × 4 baselines × 3 endpoints;
- minimum 5 trials/task;
- hard cap 50 trials/task.

If required trials/task > 50 => `UNDERPOWERED`. Do not lower alpha/margins post hoc.

## 5. Lock confirmatory tree

Before inspecting confirmatory outcomes, hash-seal:

- repo commit;
- environment;
- tasks;
- models;
- tools;
- scorer;
- baselines;
- DGC policy;
- pricing;
- budgets;
- trial count;
- statistical plan.

Only governance policy may differ across baseline/DGC arms.

## 6. Run confirmatory paired trials

Execute every confirmatory task with every policy using the frozen repeated-trial count.

Every trial must emit:

- unique `trial_id` + `task_id`;
- accepted-success outcome;
- normalized quality;
- catastrophic regret;
- complete physical cost certificate for all product cost components;
- coverage/abstention state;
- execution certificate;
- raw provider/tool usage identifiers where applicable.

Missing telemetry => trial is invalid, not zero-cost.

## 7. Run P9 simultaneous gate + CCF audit

For each family call the multi-baseline paired certificate with family alpha `0.025`.

Required against **all B0-B3**:

- cost lower bound > 0;
- quality lower bound >= `-0.02`;
- catastrophic-regret lower bound >= `-0.01`;
- full matched coverage;
- identical paired population digest.

Any baseline failure => no primary real-workload product claim.

On the same frozen counterfactual option population, also report CCF:

- DGC value regret relative to the exact available option-set optimum;
- minimum cost required to match/exceed DGC value without worse declared latency/risk;
- avoidable DGC cost under the frozen option set.

CCF is an audit upper bound over observed options, not a production policy or a claim about unobserved actions.

## 8. Evaluate commercial target separately

Only after P9 passes calculate full-cost net saving and CPS improvement.

`NetSaving >= 0.30` is a commercial target, not a scientific gate.

Never infer 30% from token reduction or from a synthetic experiment.

## 9. Freeze DGC and run G1-G5

Without policy retuning run:

- G1 unseen tasks;
- G2 unseen domain;
- G3 unseen model/provider;
- G4 changed economics/prices/latency constraints;
- G5 perturbation/countermodel shift.

Every axis must preserve quality/regret/coverage gates and positive cost-effect direction. Any retuning invalidates this generalization generation.

## 10. Independent replication

Provide an external party the exact hash-bound replication package.

Self-replay does not count.

The independent result must bind to the package digest, keep methodology unchanged and be concordant with preregistered quality/cost/regret bounds.

## 11. Seal P19 evidence bundle

Populate all required files in `artifacts/dgc-product-v1/` with actual results, not placeholders, then generate `SHA256SUMS` and run:

```bash
PYTHONPATH=. python scripts/dgc_product_bundle_gate.py
```

Any missing/unhashed/tampered file => FAIL.

## 12. Promote only through machine gate

Set evidence-status fields from generated certificates, never manually from an interpretation.

Run:

```bash
PYTHONPATH=. python scripts/dgc_product_promotion_gate.py --require-stage PRODUCT_QUALIFIED
```

Only after PASS may a `dgc-product-*` release tag be created.

## 13. Production authority remains separate

After PRODUCT_QUALIFIED:

1. shadow mode with DGC control authority = false;
2. preregistered shadow qualification;
3. bounded canary <=10% traffic with hard spend/tool/step/time/concurrency caps and automatic baseline rollback;
4. only then consider broader production control.

## Current immediate blockers

1. The current sandbox cannot complete binary/network materialization even though upstream SWE/T-Bench source identities are independently verified. Therefore local `MATERIALIZED_VERIFIED` receipts are absent.
2. The current execution environment has neither `OPENAI_API_KEY` nor `ANTHROPIC_API_KEY`; therefore no valid live provider confirmatory run can be executed here.
3. GitHub Actions has continued to terminate before repository steps; this remains `CI_EXECUTION_UNAVAILABLE`, not code PASS/FAIL.

None of these blockers may be replaced by synthetic provider traces or manually promoted status fields.
