# PREREGISTRATION — WP15 Compute-Equivalent Pareto (L7 protocol, synthetic instantiation)

**Committed before the run (separately — breaking this run's batching pattern).** AC1 established
identifiability (a gap exists). This tests the actual efficiency claim — the **accuracy-vs-total-
compute Pareto frontier** — the exact shape L7 asks. It runs on the synthetic AC1 mechanism; the
same harness, with a real workload + MoD/MoE baselines, is the cloud-ready L7.

## Synthetic confirmatory (this run)

From the committed AC1 raw seeds, difficulty prior uniform: the fixed-K frontier (accuracy vs avg
compute = K) vs the adaptive oracle allocation (each difficulty uses its best K; avg compute =
E[best K]). Interpolate the fixed frontier at the adaptive's compute; check dominance.

- **SYNTHETIC_COMPUTE_PARETO_DOMINATES** iff adaptive advantage at matched compute `> 0.05` AND
  adaptive accuracy ≥ every fixed policy at ≥ its compute.
- **NO_PARETO_DOMINANCE** otherwise.

## The cloud-ready L7 protocol (NOT run here — CWC-L7-pareto stays NOT_TESTED)

The real-workload L7 experiment, ready to run when a checkpoint + cloud budget exist, swaps only the
model/data/baselines into this harness:
1. **Workloads:** ≥2 real tasks (e.g., language modeling + a reasoning eval).
2. **Adaptive system:** the identified controller routing compute (depth / early-exit) by inferred
   difficulty, with the route-decision cost charged.
3. **Baselines:** best fixed-compute model; Mixture-of-Depths; Mixture-of-Experts — each tuned.
4. **Matched compute:** total FLOPs equalized across systems (± 1%), including controller overhead.
5. **Metric:** quality (accuracy/loss) at matched FLOPs, held-out, bootstrap 95% CI, δ=0.05,
   family-wise corrected; adaptive must Pareto-dominate on ≥2 workloads.
6. **Then L8:** independent clean-room replication.
This preregistration is the frozen L7 decision rule; only cloud compute is missing.

## Scope

Tier `SYNTHETIC`. A distinct claim from AC1 (Pareto dominance ≠ identifiability). New claim
`CWC-L7s-synthetic-pareto` (SUPPORTED on synthetic); `CWC-L7-pareto` (real) stays NOT_TESTED.
