# CWC-FLAGSHIP-ROUTE-01 — Results

Date: 2026-08-11
Scientific verdict: `CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED`
Tier: `REAL-DATA / SMALL-MODEL / INTERNAL-CORPUS MECHANISM GATE`

## Frozen question

Can one CALIBRATION-fitted decision-relevant router, using only the 65-dimensional block-1 pre-decision representation, allocate a second Transformer block better than the fixed-depth Pareto frontier and matched generic controls on both frozen real-data families, across every fresh PRIMARY seed and again in REPLICATION, under exact logical-FLOP accounting?

## Temporal provenance

- parent preregistration: `cc1609ad6b944c613737c8103fc3d695ec9b31c9`
- sensor/compute amendment 001: `bbf2ef90eafefd19b7f60e185d82b26c95f795dc`
- Pareto-frontier amendment 002: `3fcc09e9cc4a91b03eef6b3c0040f35a598dbf28`
- implementation: `61771ad`
- pre-PRIMARY hermeticity amendment 003: `4023fa9`
- serialization-only implementation repair: `cb7857b`
- frozen CALIBRATION artifact commit: `9cab08f`

No PRIMARY or REPLICATION model output existed before the calibration policy was committed.

## Calibration

Calibration seed: `74101`.

- PROSE: depth1 CE `2.7539682053`; depth2 CE `2.7151482068`; frozen gain/FLOP slope `5.6887987377e-09`.
- CODE: depth1 CE `2.6365900619`; depth2 CE `2.5878943924`; frozen gain/FLOP slope `7.1360091169e-09`.
- calibration checkpoint SHA-256: `97b45d3e3f66a133704ae864e588fbdd3fcd97a8a17a188cef860727a4049490`.
- calibration policy SHA-256: `4e64318bfe32a76c22056bdb5ec0b8c63d19b312fe5ae8a44ff802713ca3e222`.

## Confirmatory execution

| Cohort | Family | Seed | Continue rate | Candidate advantage vs fixed frontier (CE) | Cell |
|---|---|---:|---:|---:|---|
| PRIMARY | PROSE | 74201 | 0.000000 | -0.0000225127 | FAIL |
| PRIMARY | CODE | 74201 | 0.000000 | -0.0000296522 | FAIL |
| PRIMARY | PROSE | 74202 | 0.835938 | +0.0006152000 | FAIL |
| PRIMARY | CODE | 74202 | 0.546875 | +0.0014434130 | FAIL |
| PRIMARY | PROSE | 74203 | 1.000000 | OUTSIDE_FIXED_FRONTIER | FAIL |
| PRIMARY | CODE | 74203 | 0.992188 | -0.0010788113 | FAIL |
| REPLICATION | PROSE | 74301 | 0.390625 | +0.0001711262 | PASS |
| REPLICATION | CODE | 74301 | 0.609375 | +0.0108461434 | PASS |
| REPLICATION | PROSE | 74302 | 0.093750 | -0.0024710775 | FAIL |
| REPLICATION | CODE | 74302 | 0.421875 | +0.0055934365 | FAIL |
| REPLICATION | PROSE | 74303 | 1.000000 | OUTSIDE_FIXED_FRONTIER | FAIL |
| REPLICATION | CODE | 74303 | 0.968750 | -0.0007484912 | FAIL |

PRIMARY cell pass count: `0/6`.
REPLICATION cell pass count: `2/6`.

The frozen verdict rule makes any PRIMARY endpoint failure irreversible by replication. Therefore the scientific verdict is `CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED`.

## Endpoint anatomy

PRIMARY endpoint pass counts across six cells:

- within fixed frontier: `5/6`
- beats fixed frontier: `2/6`
- beats random matched: `1/6`
- no worse than hidden-norm matched: `5/6`
- beats difficulty matched: `1/6`
- oracle sanity: `6/6`
- matched counts: `6/6`

REPLICATION endpoint pass counts:

- within fixed frontier: `5/6`
- beats fixed frontier: `3/6`
- beats random matched: `4/6`
- no worse than hidden-norm matched: `4/6`
- beats difficulty matched: `4/6`
- oracle sanity: `6/6`
- matched counts: `6/6`

## What was killed

The frozen mechanism claim is not supported: a single cross-seed linear gain predictor in the raw mean-hidden-state coordinate system does not stably convert second-layer value heterogeneity into Pareto improvement across the two frozen real-data families and fresh model seeds.

This blocks architecture promotion from this branch.

## What was NOT killed

`ORACLE_HEADROOM_DIAGNOSTIC.json` is post-hoc and non-promoting. Exhaustive target-dependent allocation over continuation counts found positive maximum oracle advantage over the fixed frontier in all `12/12` cells, ranging from `0.0124020848` to `0.0217229631` CE with best continuation rates between `0.4375` and `0.53125`. Thus the negative is not evidence that adaptive allocation opportunity is absent.

`SAME_MODEL_CALIBRATION_DIAGNOSTIC.json` is also post-hoc and non-rescuing. Refitting the same ridge form on each model's own CALIBRATION representation produced `6/12` cell PASS instead of `2/12` under the frozen shared router. This identifies cross-seed hidden-coordinate nonalignment as part, but not all, of the failure; PROSE remained unstable.

Neither diagnostic can rescue the confirmatory verdict.

## Independent recomputation

`scripts/verify_cwc_flagship_route_01.py` independently recomputes continuation counts, policy losses, logical FLOPs, fixed-frontier loss, endpoints and the final verdict from serialized raw decisions without importing the routing evaluator. It reproduces:

- PRIMARY `0/6` PASS
- REPLICATION `2/6` PASS
- final verdict `CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED`

Its verifier self-test kills `5/5` serialized-result mutations.

## Relation to the programme flagship

This result is stronger than the historical WP18 stop signal for this mechanism because the comparison is performed directly in quality-vs-logical-FLOP space; no conversion of a FLOP ratio into utility units is required.

It still does **not** prove the broad H-L7 null. H-L7 remains `NOT_TESTED`: its current H1 is existential over “>=2 real workloads”, so no finite negative workload set globally falsifies it, and this experiment does not include full MoD/MoE comparator implementations. The correct current boundary is therefore:

- this two-exit shared-router adaptive-depth branch on the frozen PROSE/CODE panel: `NOT_SUPPORTED`;
- adaptive allocation as a general mechanism: `NOT_KILLED` (oracle headroom exists descriptively);
- full architecture L7 Pareto dominance: `NOT_TESTED`;
- external REAL-TRANSFER-01: `NOT_TESTED`.
