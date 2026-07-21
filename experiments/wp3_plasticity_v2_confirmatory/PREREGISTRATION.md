# PREREGISTRATION — L4 Plasticity Cost-Budget CONFIRMATORY run

**Committed before the confirmatory run.** Freezes the design so the verdict cannot
be reverse-engineered. This is the confirmatory experiment the Act-J pilot
(`artifacts/act-j-pilot-decision/`, verdict `PILOT_GO_L4_CONFIRMATORY`) green-lit.

## Motivation and what changes vs the pilot

The cost-budget plasticity "revival" (oracle gap `G ≈ 0.19` at `λ=1`) was **discovered**
on seeds 0–4 with `λ` selected post-hoc over a grid. That is exploratory: the effect
could be an in-sample / selection artifact. This run tests it **out-of-sample** with
`λ` **frozen a priori**, so no selection correction is needed and `δ = 0.05` is applied
directly.

## Frozen design

- **Mechanism (unchanged):** `experiments/wp3_plasticity_v1/src/runner_oracle.py` — real
  torch GroupedModel, pretrain on BASE, adapt one parameter group per task under the
  plasticity optimizer, measure `new_acc` + retention. Contexts C = {lexical, relational};
  actions A = {attn, mlp, head, embed}; `params_max = 8192`.
- **Fresh held-out seeds:** `5,6,…,20` (16 seeds), DISJOINT from the pilot/exploratory
  seeds 0–4. Written to a SEPARATE dir `artifacts/wp3-plasticity-v2-confirmatory/raw_runs`;
  the sealed `wp3-plasticity-v1` bundle is never touched.
- **Frozen operating point:** `λ = 1.0` (fixed a priori — NOT swept here).
- **Cost-budget utility:** `U_λ[t,a] = new_acc[t,a] − λ · cost_params[a]/params_max`.
- **Oracle gap (per seed):** `G_s = mean_t max_a U_λ[t,a] − max_a mean_t U_λ[t,a]`
  (context-blind fixed vs context-aware oracle, uniform task prior).
- **Certificate:** aggregate `Û` = mean over the 16 seeds; per-cell `se = std/√16`;
  `std_error` = max cell `se` (conservative). `G_lo =
  gap_lower_confidence_bound(Ĝ, std_error, |C|=2, |A|=4, δ=0.05)`
  (`experiments/common/identifiability_inference.py`).
- **Route cost:** given-task regime ⇒ `c_route = 0`; report route-cost headroom `= G_lo`.

## Decision rule (FROZEN)

- **Primary:** `G_lo(δ=0.05) > c_route`.
- **Robustness:** worst-seed `G_s` and the fraction of seeds with `G_s > 0`.
- **Verdicts:**
  - `L4_IDENTIFIABLE_CONFIRMED_SYNTHETIC` — primary holds, controls pass, AND
    worst-seed `G_s > 0` (effect present in every held-out seed).
  - `L4_IDENTIFIABLE_CONFIRMED_WEAK` — primary holds and controls pass, but at least
    one seed has `G_s ≤ 0` (aggregate-only).
  - `L4_NOT_CONFIRMED` — primary fails (`G_lo ≤ 0`).
  - `L4_VOID` — any control fails.

## Controls (mandatory)

- **NEGATIVE A (weak interaction):** same 16 seeds at `λ = 0` (unconstrained). Expect
  aggregate `G_lo ≤ 0`.
- **NEGATIVE B (quality dominance):** routing matrix `[[1,1],[0.004,1]]` under the plug-in
  gap at the run's noise level. Expect `G_lo ≤ 0`.
- **POSITIVE (specialization):** `[[1,0],[0,1]]` at the run's noise level. Expect `G_lo > 0`.
- **Certificate self-falsification:** `falsify_inference().all_ok`.

## Scope / prohibited extrapolations

Tier `SYNTHETIC` (same synthetic task family and toy GroupedModel as WP3). A positive
verdict confirms the cost-budget plasticity oracle gap is real and out-of-sample on this
benchmark under a frozen budget — it does **NOT** establish: a learned governor achieves
it, compute-equivalent Pareto (L7), energy/latency advantage, real-workload
generalization, or independent replication. L4 registry status advances only to
`SUPPORTED_NARROWED` (synthetic, oracle, no learned controller) on confirmation, never to
an L7 claim.
