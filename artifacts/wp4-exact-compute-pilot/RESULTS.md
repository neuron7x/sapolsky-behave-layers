# WP4 Exact-Total-Compute Pilot

Status: **`EXPLORATORY_PILOT_NOT_PREREGISTERED`**.

Adaptive halt and the input-blind control receive exactly the same integer total
hop budget in every `(distribution, data_seed)` cell. The control uses the
lowest-variance input-blind floor/ceiling allocation and randomly permutes it
across examples; 16 allocation permutations are averaged per data seed.

| Distribution | Mean paired solved difference | Exploratory bootstrap 95% CI |
|---|---:|---:|
| uniform | 0.4344 | [0.4334, 0.4354] |
| easy_skew | 0.3200 | [0.3116, 0.3284] |
| hard_skew | 0.5173 | [0.5117, 0.5236] |
| bimodal | 0.4852 | [0.4773, 0.4947] |

## Prohibited interpretation

This does not license a confirmatory or Pareto claim. The exact total budget is
derived from the pilot batch's aggregate difficulty, the adaptive policy has an
exact convergence oracle, examples are synthetic, and no controller inference
cost exists. The pilot exists to validate the next protocol and power model.
