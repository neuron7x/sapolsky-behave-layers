# DGC Product v1 — Baseline Panel

Required preregistered policies:

- `B0_FIXED_COMPUTE`
- `B1_UNCERTAINTY_ROUTER`
- `B2_LEARNED_COST_QUALITY_ROUTER`
- `B3_SEQUENTIAL_VERIFICATION`
- candidate: `B4_DGC`

The class identities are frozen. The executable baseline panel is **not yet frozen** because B2 must be fitted using calibration-only tasks from the materialized external workload and then bound to `calibration_task_digest` + `fitted_model_digest` through `cwc/governance/baseline_panel.py`.

No post-confirmatory replacement of a strong baseline with a weaker implementation is allowed. Product success requires DGC to pass the simultaneous preregistered cost/quality/catastrophic-regret gate against every admissible B0-B3 baseline on the same paired trial population.
