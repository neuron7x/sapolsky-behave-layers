# DGC-01 Development Oracle Pilot — Results

**Authority:** DEVELOPMENT_ONLY / NON-PROMOTING. `CWC-DGC-H1` remains `NOT_TESTED`.

Tasks: 100000 paired synthetic tasks (20000 per frozen regime A-E).

## Policy outcomes

| Policy | Mean NetDecisionValue | Compute rate | Decision error rate | Mean compute cost |
|---|---:|---:|---:|---:|
| B0_FIXED | -0.078522461 | 1.000000 | 0.000000 | 0.078522461 |
| B1_UNCERTAINTY | -0.099428128 | 0.600000 | 0.087160 | 0.060009598 |
| B2_COST_QUALITY_ROUTER | -0.081030049 | 0.800000 | 0.009330 | 0.067023353 |
| B3_DGC | -0.038513334 | 0.600000 | 0.000000 | 0.038513334 |

DGC oracle-routing agreement: `1.000000`; false-stop: `0.000000`; false-escalation: `0.000000`.

## Paired DGC deltas

| Baseline | Mean delta | Anytime CS lower | Anytime CS upper |
|---|---:|---:|---:|
| B0_FIXED | 0.040009127 | 0.038609378 | 0.041408875 |
| B1_UNCERTAINTY | 0.060914794 | 0.042193161 | 0.079636426 |
| B2_COST_QUALITY_ROUTER | 0.042516715 | 0.023795083 | 0.061238347 |

Confidence sequences use frozen generator-support bounds and `STITCHED_HOEFFDING_UNION_BOUND_V1`.

The 136 MiB raw JSONL is deterministic derived data and is not committed; `raw_results_digest.json` binds its SHA-256, byte count, line count and exact regeneration command.

## Interpretation boundary

- Development execution only; not an untouched confirmatory cohort.
- Exact oracle agreement is expected because this synthetic arm is given the declared prior/utility/cost model, but never the realized hidden world.
- A separate misspecification falsifier demonstrates that this advantage can reverse when the belief model is wrong.
- No real-world calibration, general superiority, production safety or novelty conclusion is permitted.
