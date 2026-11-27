# DGC Product Qualification — Execution Runbook v1

Protocol snapshot: 2026-09-27. Operational review: 2026-11-27.

## Status and evidence

The reference checkout for this review is `78eed8b4a5516a9e4e44e4912011dd653b6127ae`.
Recheck the checkout and replay the relevant gate when reviewing a later revision.

| Scope | State at review | Authority |
| --- | --- | --- |
| Canonical source registry | Two frozen source identities replayed. The registry carries zero materialized and zero executed families. | [Registry](../artifacts/dgc-product-v1/external_source_authority.json) · [Source gate](../scripts/dgc_product_external_source_gate.py) |
| Separate materialization replay | 500 SWE-bench Verified and 89 Terminal-Bench 2.1 tasks verified at the reference checkout. | [Receipt at draft #105 head](https://github.com/neuron7x/sapolsky-behave-layers/blob/d4a75d4edd184a8895d40a7500e9051395ad66d6/artifacts/dgc-product-v1/materialization-receipts/78eed8b.json) |
| Synthetic financial experiment | The frozen synthetic threshold passed. Client verification and commercial authority are both false. | [Replay and limits](../artifacts/dgc-02-finance-confirmatory/RESULTS.md) |
| Mechanism protocol | Cost and quality with exact matched coverage. External execution, fitted B2 and calibration-based sizing are outstanding. | [Mechanism protocol](DGC_PREINFERENCE_MECHANISM_LANE_v1.md) |
| Product | The qualification pointer is inactive. The three-endpoint product plan requires a prespecified catastrophic-regret endpoint for each family. | [Pointer V3](../artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json) · [Closure executor](DGC_EVIDENCE_CLOSURE_EXECUTOR_v1.md) |

[Draft #105](https://github.com/neuron7x/sapolsky-behave-layers/pull/105)
also proposes the mechanism partition CLI, the V5.1 Route B decision and the
tagged release checkout fix. [Draft #106](https://github.com/neuron7x/sapolsky-behave-layers/pull/106)
proposes an offline maximin verification-value evaluator. Both changes were
unmerged at review time. Their checks apply to the tested revisions.

## Read-only preflight

Run from the repository root with Git and Python 3.11 or newer. These checks
use local repository records and require no provider credentials or images.

```bash
git rev-parse HEAD 'HEAD^{tree}'
git status --porcelain=v1
PYTHONPATH=. python -B scripts/dgc_product_external_source_gate.py
PYTHONPATH=. python -B scripts/dgc_product_promotion_gate.py --require-stage RESEARCH_HYPOTHESIS
PYTHONPATH=. python -B scripts/dgc_product_promotion_gate.py --require-stage PRODUCT_QUALIFIED
```

On the reference checkout, the source gate reports `2/2` and exits 0, the
research-stage check exits 0, and the final command exits 1 with
`product qualification pointer is not activated`. A different failure message
requires investigation. The nonterminal check validates the status mirror.
The terminal check replays the qualification pointer and append-only packaging
authority. To replay the local DGC contracts and synthetic finance controls:

```bash
umask 022
make -f Makefile.cwc dgc-gate dgc-financial-gate PY=python
```

Use the repository test environment documented in the
[test and CI reference](vnv/CWC_TEST_AND_CI_REFERENCE.md).

The following sections describe the evidence prerequisites for completing an
external generation. On the reference checkout the mechanism partition CLI
and the product risk endpoints are still blockers.

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

Install the dedicated materialization environment from the repository root:

```bash
python -m venv eval_bundle/dgc-materialization-venv
source eval_bundle/dgc-materialization-venv/bin/activate
python -m pip install -r dgc-external-requirements.txt
```

Use a clean checkout and a fresh generation ID. Keep these variables in the
same shell through the materialization and reference steps. Git ignores the
runtime directory.

```bash
DGC_GENERATION=source-replay-001
MATERIALIZATION_ROOT="eval_bundle/dgc-external/${DGC_GENERATION}"
MATERIALIZATION_REFERENCE="eval_bundle/dgc-external/${DGC_GENERATION}-reference.json"

PYTHONPATH=. python scripts/dgc_materialize_external_sources.py \
  --output-root "$MATERIALIZATION_ROOT"
```

The command emits `MATERIALIZATION_RECEIPT.json` only after both families pass byte/Git identity checks. Receipt fields keep `execution_authorized=false` and `product_promotion_authorized=false`.
For offline replay, pass `--swe-parquet` with the pinned Parquet file and
`--terminal-repo` with a clean checkout of the pinned Git revision. Both
options use the same identity checks. Use a new generation ID for a retry.

### SWE-bench Verified

Frozen revision:

`03e151cf5560b1af6a4363c6a9d766deaaea6b56`

Frozen parquet SHA-256:

`bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`

Expected: `500` unique `instance_id` values.

On a hash, count or uniqueness mismatch, stop and recover the pinned input.
A deliberate source revision change requires a new source authority and
preregistration before outcomes are inspected.

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

### 1.1 Import the verified materialization reference

The build and execution layers consume the verified reference, not the materialization directory by convention alone.

```bash
PYTHONPATH=. python scripts/dgc_import_materialization_reference.py \
  --generation-root "$MATERIALIZATION_ROOT" \
  --output "$MATERIALIZATION_REFERENCE"
```

Required result:

- reference schema: `DGC_EXTERNAL_EVIDENCE_REFERENCE_V2`;
- repository commit/tree equal the clean current DGC checkout;
- Terminal-Bench binding contains the frozen 89-task manifest and the exact `repo/tasks` workload-tree SHA-256;
- no execution or product authority is created.

To record both source stages in the closure ledger, keep the same Python
environment on `PATH` and use the same generation:

```bash
PYTHONPATH=. python scripts/dgc_close_external_materialization.py \
  --generation-id "$DGC_GENERATION" \
  --generation-root "$MATERIALIZATION_ROOT"
```

The ledger and its reference are under
`eval_bundle/dgc-evidence-closure/<generation-id>/`. The expected next stage
is `EXECUTION_MANIFESTS_FROZEN`.

### 1.2 Build and freeze the Terminal-Bench task-scoped OCI population

Terminal-Bench 2.1 does **not** have one global sandbox image. The frozen population contains 89 task environments, so each task must be bound to its own registry-resolved immutable OCI identity.

Use a fresh runtime output root and a registry namespace with no mutable tag:

```bash
TERMINAL_TASKS="$MATERIALIZATION_ROOT/TERMINAL_BENCH_2_1/repo/tasks"
SANDBOX_GENERATION=eval_bundle/dgc-terminal-sandboxes/gen-001
: "${DGC_OCI_REGISTRY_PREFIX:?set the authorized OCI registry and namespace}"

PYTHONPATH=. python scripts/dgc_build_terminal_sandbox_images.py \
  --tasks-root "$TERMINAL_TASKS" \
  --materialization-reference "$MATERIALIZATION_REFERENCE" \
  --registry-prefix "$DGC_OCI_REGISTRY_PREFIX" \
  --output-root "$SANDBOX_GENERATION"
```

This step performs image builds and registry pushes but **does not execute benchmark agents**. Authority is minted only after the complete 89-task generation replays successfully.

The generation must contain:

- one canonical build receipt per frozen task;
- exact task-source and `environment/` build-context SHA-256 identities;
- registry-resolved `repo@sha256:...` image references;
- separate receipt file SHA-256 and semantic receipt digest;
- `SANDBOX_IMAGE_POPULATION.json`;
- `ENVIRONMENT_MANIFEST.json` using `DGC_ENVIRONMENT_MANIFEST_V2`;
- atomic generation receipt/provenance with `external_benchmark_execution_performed=false`.

Any missing task, extra receipt, task/context substitution, registry-manifest digest mismatch, mutable image reference, symlink escape, or generation replay failure => STOP. Partial registry pushes do not constitute evidence authority.

## 1.3 Verify the frozen OpenAI two-tier candidate panel

Before composing the complete execution freeze, verify the pre-execution model/action/pricing candidate authority:

```bash
PYTHONPATH=. python scripts/dgc_openai_snapshot_panel_gate.py
```

Frozen candidate identities:

- `STANDARD`: `codex@0.157.1` + `openai/gpt-5.4-nano-2026-03-17`;
- `DEEP`: `codex@0.157.1` + `openai/gpt-5.4-mini-2026-03-17`.

Both model IDs are dated OpenAI snapshots. The gate requires exact action/model/pricing population closure, official OpenAI pricing-source URLs, exact Codex semver, and strict cost monotonicity `STANDARD < DEEP` for input/cached-input/output token rates.

This is a **candidate execution panel**, not outcome evidence. It keeps `executable_evidence_observed=false` and `product_promotion_authorized=false`. The complete harness still requires the materialized workload, prompt/tool/budget/scorer/environment identities and final execution freeze.

## 2. Freeze content-addressed execution manifests

For each workload family produce SHA-256 content identities for:

- materialization receipt and task manifest;
- scorer/evaluator source;
- frozen `catastrophic_regret` endpoint implementation + semantics contract;
- environment/container images;
- model IDs/versions and model manifest;
- one global action catalog binding every action ID to exact Harbor agent/version + provider/model/version;
- prompt/system policy;
- tools;
- maximum per-task budget;
- provider pricing snapshot;
- DGC governance policy;
- product statistical plan.

Semantic labels such as `model-v1` are not evidence identities. `FrozenEvaluationHarness` requires lowercase SHA-256 manifests.

## 2M. Mechanism lane: use the risk-free execution freeze

The real-workload mechanism lane MUST NOT use the product execution freeze, because SWE-bench Verified and Terminal-Bench 2.1 do not provide the frozen product `catastrophic_regret` endpoint.

Prepare `DGC_MECHANISM_EXECUTION_FREEZE_INPUT_V1` with the same common execution identities as Section 2 **except** `risk_endpoint_manifest`. Any risk endpoint in this input is a hard error.

```bash
PYTHONPATH=. python scripts/dgc_freeze_mechanism_execution.py \
  --input eval_bundle/MECHANISM_EXECUTION_FREEZE_INPUT.json \
  --output eval_bundle/MECHANISM_EXECUTION_FREEZE.json
```

Required result:

- schema `DGC_MECHANISM_EXECUTION_FREEZE_V1`;
- exactly 11 common components;
- `risk_endpoint_bound=false`;
- exact materialization, model/action/pricing, observation, executor, scorer, budget and governance-policy identities;
- `mechanism_execution_authorized=false`;
- `product_promotion_authorized=false`.

The product freeze remains unchanged and still requires the risk endpoint.

## 3M. Mechanism lane: fit B2 on quality + cost only

Before fitting B2, the mechanism lane needs a task-partition receipt bound to
the risk-free execution freeze. The CLI on the reference checkout accepts
the product freeze only. Stop at this dependency until a mechanism partition
producer is available in the checkout. [Proposed CLI](https://github.com/neuron7x/sapolsky-behave-layers/pull/105)

Do not feed synthetic or post-outcome risk labels into B2. Prepare `DGC_MECHANISM_B2_FIT_INPUT_V1` with:

- frozen `MechanismLearnedRouterConfig`;
- complete calibration `task × action` counterfactual table;
- only `quality` and `cost_usd` outcomes;
- exact forbidden confirmatory + G1 task IDs;
- frozen feature-schema and training-algorithm digests.

```bash
PYTHONPATH=. python scripts/dgc_fit_mechanism_b2.py \
  --input eval_bundle/MECHANISM_B2_FIT_INPUT.json \
  --output eval_bundle/MECHANISM_B2_FIT_RECEIPT.json

PYTHONPATH=. python scripts/dgc_authorize_mechanism_b2.py \
  --execution-freeze eval_bundle/MECHANISM_EXECUTION_FREEZE.json \
  --task-partition eval_bundle/TASK_PARTITION.json \
  --fit-input eval_bundle/MECHANISM_B2_FIT_INPUT.json \
  --fit-receipt eval_bundle/MECHANISM_B2_FIT_RECEIPT.json \
  --output eval_bundle/MECHANISM_B2_FIT_AUTHORITY.json
```

Any `catastrophic_regret`, `risk`, `risk_score` or `risk_endpoint` field in mechanism B2 input => STOP.

After B2 fit authority is available, freeze the final risk-free comparison harness:

```bash
PYTHONPATH=. python scripts/dgc_build_mechanism_harness_freeze.py \
  --execution-freeze eval_bundle/MECHANISM_EXECUTION_FREEZE.json \
  --mechanism-b2-authority eval_bundle/MECHANISM_B2_FIT_AUTHORITY.json \
  --baseline-panel-input eval_bundle/BASELINE_PANEL_INPUT.json \
  --output eval_bundle/MECHANISM_HARNESS_FREEZE.json
```

The execution-authority builder requires the mechanism-specific freeze, this
harness, the matching partition and a calibration-bound sizing receipt.
The [mechanism protocol](DGC_PREINFERENCE_MECHANISM_LANE_v1.md#frozen-mechanism-execution-authority)
defines their evidence boundaries.

## 3. Fit B2 on calibration tasks only

B0/B1/B3 use frozen policy contracts. Product B2 learns from quality, cost
and catastrophic regret. Fit it only after the task split is frozen.

Prepare `DGC_B2_FIT_INPUT_V1` containing:

- frozen `LearnedRouterConfig`;
- complete calibration `task × action` counterfactual table;
- explicit forbidden task IDs covering confirmatory and held-out tasks;
- expected feature-schema SHA-256;
- expected training-algorithm SHA-256.

Run:

```bash
PYTHONPATH=. python scripts/dgc_fit_b2_baseline.py \
  --input "eval_bundle/dgc-calibration/$DGC_GENERATION/B2_FIT_INPUT.json" \
  --output "eval_bundle/dgc-calibration/$DGC_GENERATION/B2_FIT_RECEIPT.json"
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
  --input "eval_bundle/dgc-calibration/$DGC_GENERATION/TRIAL_SIZING_INPUT.json" \
  --output "eval_bundle/dgc-calibration/$DGC_GENERATION/TRIAL_SIZING_RECEIPT.json"
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
- catastrophic regret computed only by the frozen family-specific risk-endpoint implementation;
- complete physical cost certificate including human/infra/retry/failure loss where applicable;
- coverage/abstention state;
- raw provider/tool usage identifiers;
- evidence digest bound to the frozen harness.

Missing telemetry => invalid trial, never zero cost.

Missing or post-outcome-defined catastrophic-regret semantics => invalid generation. Benchmark pass/fail must not be silently re-labeled as catastrophic regret. If a workload family lacks a scientifically defensible pre-outcome risk endpoint, re-preregister a new statistical-plan generation before inspecting confirmatory outcomes.

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

All baselines must pass both the exact-panel and V5.1 anytime-valid criteria.
See the [P9 contract](DGC_EVIDENCE_CLOSURE_EXECUTOR_v1.md#6-confirmatoryp9-contract)
for statistical scope and evidence requirements.

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
PYTHONPATH=. python scripts/dgc_release_repro_gate.py --require-product-qualified
```

Only after all PASS may a `dgc-product-*` release tag be created.

## 14. Production authority remains separate

After `PRODUCT_QUALIFIED`:

1. shadow mode with DGC control authority = false;
2. preregistered shadow qualification;
3. continuous assurance across functionality/operations/human/security/compliance/large-scale-impact evidence;
4. bounded canary <=10% traffic with hard spend/tool/step/time/concurrency caps and automatic rollback;
5. only then consider broader production control.

## Blocker records

Read observations with their recorded revision or date. The 2026-09-27
runbook captured the pre-execution and runner blockers for that snapshot.

1. Source-materialization replay on `78eed8b4a5516a9e4e44e4912011dd653b6127ae`
   sealed 500 SWE-bench Verified and 89 Terminal-Bench 2.1 tasks across 1,104
   files. [Materialization receipt](../artifacts/dgc-product-v1/materialization-receipts/78eed8b.json).
   Publication manifest SHA-256
   `c529eea4d521bee31e91ccd74d991859874608f557c60af955cc93ecfc433144`.
   Independent verification reconstructed the Terminal Git tree and rejected a
   one-byte change to the SWE-bench parquet. Execution manifests and
   task-scoped OCI build receipts still need verified materialization for the
   chosen execution host.
2. No valid live provider confirmatory population has been executed in this environment.
3. B2 has no external calibration fit receipt yet.
4. Calibration-only between/within-task variance components and final repeat count are not yet measured externally.
5. V5.1 product confirmatory execution for both external families is retired
   under [issue #17](DGC_PREINFERENCE_MECHANISM_LANE_v1.md#pre-outcome-decision-for-issue-17).
6. Hosted [DGC semantics and executor regressions](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45770838909/job/139742825525)
   passed on `0bebec18f51aabfc554dd35b6a74dd0e1021c989`. The tagged product release remains unexercised.
7. Independent replication/review and real multi-node/cloud operational evidence are absent.

None of these blockers may be replaced with synthetic traces, manually promoted status fields or prose claims.
