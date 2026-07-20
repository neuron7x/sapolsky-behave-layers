# PREREGISTRATION — Act-J Identifiability Pilot (decision instrument)

**Committed before the confirmatory run.** This freezes the decision rule so the
GO/NO-GO cannot be reverse-engineered from the result.

## Question

Before spending confirmatory (and eventually cloud) compute on an adaptive-control
mechanism, decide — with a bounded false-positive rate — whether the mechanism is
**identifiable** (oracle gap `G > 0`) and whether its **net value** clears the
route-decision cost (`G − c_route > 0`). This is the §6 identifiability predictor +
the calibrated certificate (`experiments/common/identifiability_inference.py`,
`docs/IDENTIFIABILITY_INFERENCE.md`) applied to the real data the lab holds locally.

## What this pilot DOES and DOES NOT decide

- **DOES:** GO/NO-GO for a *confirmatory cost-aware plasticity run* (the concrete
  L4 next step) using the real `wp3-plasticity-v1` oracle-gap measurements.
- **DOES NOT:** decide L7 (compute-equivalent Pareto vs MoD/MoE on real LM
  workloads). No trained checkpoint exists locally, so no live LM pilot is run.
  This pilot is **offline identifiability**, not a compute-Pareto or a learned
  controller. It cannot green-light L7; it can only refuse or advance L4.

## Data (frozen, real)

`artifacts/wp3-plasticity-v1/oracle-gap/raw_runs/seed{0..4}.json` — 5 seeds, real
measured `new_acc` and `cost_params` for contexts C = {lexical, relational} tasks
and actions A = {attn, mlp, head, embed} parameter groups. `params_max = 8192`.

## Utility, estimator, noise

- Cost-budget utility: `U_λ[t,a] = new_acc[t,a] − λ · cost_params[a]/params_max`.
- Per-cell estimate `Û[t,a]` = mean over the 5 seeds.
- Per-cell standard error `se[t,a] = std_seed[t,a] / √5`. The certificate takes a
  single homoskedastic `std_error`; we use the **max** cell `se` (conservative).
- `|C| = 2`, `|A| = 4`.

## Decision rule (FROZEN)

- Confidence: `δ = 0.05`.
- `λ` was identified post-hoc over the grid `Λ = {0.0, 0.5, 1.0, 2.0}`, so the GO
  decision applies a **Bonferroni selection correction**: `δ_eff = δ/|Λ| = 0.0125`.
- Certificate: `G_lo(λ) = Ĝ(λ) − sd√(2ln|A|) − (sd/√|C|)√(2ln(2/δ_eff))` via
  `gap_lower_confidence_bound`.
- Route cost: primary regime is **given-task** (the task identity is observed at
  training time, so selecting the group is a table lookup) ⇒ `c_route = 0`. We
  additionally report the **route-cost headroom** `= G_lo` (the largest `c_route`
  the decision survives) so the given-task assumption is auditable.
- **GO** (advance to the L4 confirmatory run) **iff** `G_lo(λ=1; δ_eff) > c_route`.
  Operating point `λ=1` is the theory-identified cost budget; `λ=1` is fixed here.

## Controls (mandatory — a pilot that cannot fail is not a pilot)

The certificate operates on the **unconstrained** plug-in gap `plugin_gap(U)`, so
each control is a utility matrix with a known true gap.

- **NEGATIVE control A (weak interaction):** the plasticity utilities at `λ = 0`.
  Theory predicts weak-interaction collapse ⇒ expect `G_lo ≤ 0`.
- **NEGATIVE control B (quality dominance):** the routing-v2 quality matrix
  `Q = [[1.00,1.00],[0.004,1.00]]`. Under the *unconstrained* plug-in gap the
  semantic path dominates (`plugin_gap = 0` by construction) ⇒ expect `G_lo ≤ 0`.
  (Its gap appears only under a hard budget — outside this certificate's object —
  which is exactly the point being tested for plasticity.)
- **POSITIVE control (specialization):** the anti-diagonal `[[1,0],[0,1]]`
  (`plugin_gap = 0.5`, no dominant choice) with a defined per-cell `se` ⇒ at a
  sufficient pilot size expect `G_lo > 0`. The certificate must green-light a
  genuinely identifiable problem, else it is uselessly conservative.
- **Certificate self-falsification:** `falsify_inference` must report
  `calibration_valid` (calibrated FPR ≤ δ) and `naive_rule_fails` on random nulls,
  else the whole instrument is void.

## Sample complexity

Report `n* = sample_complexity(Ĝ(λ=1), σ_max, |C|, |A|, δ_eff)` — the per-cell
pilot size that would guarantee `G_lo>0` at the observed gap. Because `Ĝ` is used as
the true-gap proxy, `n*` is **optimistic** and is reported as guidance, not a bound.

## Verdicts

- `PILOT_GO_L4_CONFIRMATORY` — negative control non-identifiable, positive control
  identifiable, certificate valid, AND `G_lo(λ=1;δ_eff) > 0`.
- `PILOT_NOGO` — primary `G_lo ≤ 0` (refuse the confirmatory spend).
- `PILOT_VOID` — any control fails (instrument not trustworthy; no decision).

Prohibited extrapolations: L7 Pareto, energy/latency advantage, learned allocator,
real-workload generalization, independent replication.
