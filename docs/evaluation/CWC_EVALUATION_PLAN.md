# CWC Evaluation Plan

## Tiers
1. **Mechanism evaluation** (current): synthetic, mechanism-separable benchmarks that
   isolate one causal question each. All shipped results are Tier 1.
2. **Controlled evaluation**: harder synthetic distributions, generalization/extrapolation.
3. **Real-workload evaluation** (NOT_TESTED): language modelling + structured
   reasoning/retrieval/code, ≥2 workloads, multiple scales — cloud.

## Primary evaluation vector
`V = (Q, FLOPs, p95_latency, VRAM, transfer, forgetting, robustness)`.
Energy is included **only** with a valid physical measurement; on this hardware it is
`INSTRUMENT_INVALID` and excluded. No arbitrary single composite score.

## Mechanism vs system
Mechanism claims (routing causality, allocation gap) are separated from system claims
(Pareto advantage). A mechanism positive never implies a system positive.

## Cost accounting (mandatory in every comparison)
controller overhead, dispatch overhead, parameter growth, optimizer state, replay &
memory cost — all counted. See `BASELINE_SELECTION_AND_COMPUTE_PARITY_POLICY.md`.

## Operating points
Report all preregistered operating points (e.g. capacity 25/50/75/100%); select the
operating point on validation only.
