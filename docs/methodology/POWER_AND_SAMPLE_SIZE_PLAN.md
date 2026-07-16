# Power and Sample Size Plan

Companion to the SAP. Sample size `n = ceil( ((z_{1-α/2}+z_{1-β})·σ_d / δ_min)^2 )`.

## Synthetic mechanism experiments (current)
Effect sizes are large and near-deterministic:
- WP4 Jensen gap: |measured − P(m>K)| = 0.0000 → any n≥2 is decisive; we use **8**.
- Routing v3 REINFORCE: learned 0.009 vs random 0.48 (huge, tiny variance) → 8 seeds give
  a paired-diff 95% UB of −0.465, far below 0.
- Surface-matched: AUROC 0.51 ± tiny; 8 seeds × 4 arms confirm chance with no loss saving.

`α = 0.05`, `power ≥ 0.80`, `δ_min` declared per protocol. For these effects, 8 seeds
exceeds the required n by orders of magnitude; the binding constraint is **not** power
but external validity (synthetic-only).

## Real-workload / Pareto claims (NOT_TESTED)
Before any cloud confirmatory run: estimate `σ_d` from a pilot, set `δ_min` to the
minimum meaningful Pareto margin, compute `n`, and preregister it. Expected `n` is
8–12 paired seeds × ≥5 corpora × baseline set — see
`docs/evaluation/BASELINE_SELECTION_AND_COMPUTE_PARITY_POLICY.md` and the cost envelope
`docs/reproducibility/EXPECTED_RUNTIME_HARDWARE_AND_COST.md`.
