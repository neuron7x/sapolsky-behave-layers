# wp15_compute_pareto — RESULTS

**Verdict: `SYNTHETIC_COMPUTE_PARETO_DOMINATES`.** Tier: SYNTHETIC — compute-equivalent Pareto (the L7 protocol, synthetic instantiation). Preregistration:
`experiments/wp15_compute_pareto/PREREGISTRATION.md` (committed separately; doubles as the L7 protocol).

## The L7-shaped result on synthetic data

| policy | avg compute | accuracy |
|---|---|---|
| fixed K=1 | 1.00 | 0.3748 |
| fixed K=2 | 2.00 | 0.3747 |
| fixed K=3 | 3.00 | 0.3755 |
| **adaptive (oracle)** | **2.00** | **0.9996** |

At **matched average compute (2.00)** the adaptive allocation reaches 1.000
accuracy vs 0.375 for the fixed frontier -- **advantage
+0.6249**, Pareto-dominating every fixed-compute policy.

At matched average compute, adaptive allocation reaches ~1.0 accuracy while every fixed-compute policy is stuck near chance (each fixed K solves only its own difficulty). This is the L7 shape (Pareto dominance at matched FLOPs) on synthetic data; the real- workload L7 is cloud-blocked (no checkpoint/budget/baselines).

**CWC-L7-pareto (real workload, MoD/MoE baselines, cloud) remains NOT_TESTED; this is the synthetic precursor and the cloud-ready protocol.** The preregistration is the frozen, cloud-ready L7 decision rule; only cloud
compute + a checkpoint + tuned MoD/MoE baselines are missing.
