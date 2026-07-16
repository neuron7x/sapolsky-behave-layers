# Preregistration — R3-C credit-assignment falsification (Routing v3 core, local)

**Registered before confirmatory run.** Commit at registration: see git log.

## Question
R3-C (end-to-end controller, label-free fixed budget, task loss only, no
counterfactual value distillation) **collapsed** under a straight-through top-K
estimator (`artifacts/wp2-routing-v3-r3c/`: learned_loss 0.91 > random 0.48,
AUROC ≈ 0). The identifiability theory says the oracle gap is **positive** under
a 50% budget (`docs/IDENTIFIABILITY_THEORY.md`: G = 0.249). So the routing signal
*exists* in the benchmark. Two mutually exclusive explanations for the collapse:

- **H_opt (optimization artifact):** straight-through is too weak a credit-assignment
  method; a policy-gradient controller *can* find the signal.
- **H_deep (deep narrowing):** the earlier SUPPORTED result was genuinely
  load-bearing on the privileged counterfactual target; no leakage-free controller
  recovers routing regardless of estimator.

## Design
Identical task (S-R-O semantic route), identical frozen path modules
(`_train_paths`), identical fixed **label-free** capacity (`FIXED_CAP_FRAC=0.5`),
identical corrected metrics (symmetric NMI, average-rank AUROC), identical eval
corpus. **Only the controller's credit-assignment differs:**

- Control arm = straight-through (existing `runner_r3c.py`).
- Test arm = **REINFORCE** with a mean-reward advantage baseline and an explicit
  per-use FLOP cost (the honest R-C objective `L = L_task + λ·C_use`): per-sequence
  Bernoulli policy `p_i = σ(need_i)`, sample `a_i`, reward `r_i = −taskloss_i − λ·a_i`,
  gradient `−(r_i − b)·log p(a_i)`. λ tuned once so the induced semantic fraction
  ≈ 0.5 (matched to the eval budget). Eval uses top-K (label-free K) for both arms
  so the comparison is fair.

## Primary metrics (per arm, ≥8 seeds)
`learned_loss`, `random_loss`, `frozen_loss`, `route_balanced_acc`,
`route_symmetric_nmi`, `route_auroc`, `semantic_used`.

## Preregistered decision rule
- **ROUTING_END_TO_END_SUPPORTED (H_opt)** iff, for the REINFORCE arm across ≥8 seeds:
  `mean(learned_loss) < mean(random_loss)` AND the paired bootstrap 95% upper bound
  of `(learned_loss − random_loss) < 0` AND `AUROC` lower 95% bound `> 0.5`.
- **ROUTING_END_TO_END_NOT_SUPPORTED (H_deep)** otherwise. In that case the
  existing narrowed claim stands and is *strengthened*: the collapse is not merely
  an estimator artifact.

Either outcome is reported. No metric or seed is dropped post hoc.

## Out of scope (honestly deferred, cloud)
Real workloads, model scale, MoD/MoE baselines, compute-equivalent Pareto. This
run isolates one variable — credit-assignment — on the existing synthetic benchmark.
