# WP5-AC2 Learned Compute-Controller — RESULTS

**Verdict: `AC2_CONTROLLER_RECOVERS`.** Preregistration:
`experiments/wp5_adaptive_compute/PREREGISTRATION_CONTROLLER.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.controller`.

## A reward-only controller recovers the compute-allocation out-of-sample

| held-out (`λ=0.5`) | value |
|---|---|
| random-`K` policy | 0.041 |
| best fixed `K` (train-chosen) | 0.208 |
| **learned controller (worst of 8 inits)** | **0.666** |
| oracle (`K=d`) | 0.666 |
| **recovery** (worst init) | **1.000** |
| NULL falsifier recovery | **0.000** |

A per-difficulty softmax REINFORCE policy, trained from **reward only** (never the oracle) on
seeds 0–3 and evaluated on held-out seeds 4–7, recovers **100%** of the oracle compute-allocation
gap in all 8 controller initializations — it learns `K=d` per difficulty. The NULL falsifier
(collapsed reward) returns 0; `random < best_fixed`.

## Consequence

The compute axis now mirrors the plasticity arc: **AC1** (allocation is identifiable) → **AC2** (a
learned reward-only controller recovers it). The identifiability→learned-controller loop is closed
on a *second* real mechanism, on the axis L7 targets.

`CWC-AC2-compute-controller` is registered **SUPPORTED**. Given-difficulty regime (the controller
sees `d`); it does NOT yet infer difficulty from the input (a follow-up), nor establish real-workload
or L7.

## Scope

Tier `SYNTHETIC`. Learned compute-controller on the second mechanism, given difficulty.
