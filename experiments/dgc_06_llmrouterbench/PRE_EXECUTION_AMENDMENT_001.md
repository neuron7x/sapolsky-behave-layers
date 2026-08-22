# DGC-06 PRE-EXECUTION AMENDMENT 001 — Simultaneous Strong-Baseline Authority

Date: 2026-08-22
Temporal status: before benchmark bundle materialization and before any DGC score execution.

The original preregistration remains unchanged. This amendment only strengthens the promotion criterion in light of a public independent reproduction artifact and the newly implemented simultaneous multi-baseline Pareto certificate.

## External competitive-null authority

Public reproduction repository: `lotusroot-kim/llmrouterbench-reproduction`.

- `README.md` blob SHA: `d168d44afe329a9cfadb7dce2c9fe79fa2d54647`.
- `results/multiseed_pareto.json` blob SHA: `85a66adf9d43d609c4ec486f1f71122cdc269c87`.
- seeds: `42, 3407, 0, 1, 2`.
- reproduced GPT-5 Best Single: approximately `65.71% / $125.6`.
- reproduced Avengers-Pro: maximum about `68.04%`; approximately `66.14% / $85.7`, reported as `31.8%` cost saving at at-least-GPT-5 accuracy.

These are aggregate competitive-null numbers. They are explicitly **not** accepted as per-query paired evidence for DGC.

## Strengthened promotion gate

After materialization and a second schema-specific amendment, DGC must use `certify_multi_baseline_pareto_improvement` on one frozen paired task population. Every reproduced strong baseline must share the exact `paired_task_digest`, sample count and coverage `1.0`.

For each baseline, simultaneous familywise inference must cover:

1. paired cost gain `C_baseline - C_DGC` with lower bound `> 0`;
2. paired quality gain `Q_DGC - Q_baseline` with lower bound at or above the preregistered noninferiority margin;
3. paired catastrophic-regret gain `R_baseline - R_DGC` with lower bound at or above its preregistered noninferiority margin.

With `K` baselines the current certificate allocates `alpha/(3K)` to each bounded paired-mean interval, giving familywise simultaneous coverage at least `1-alpha` by the union bound without requiring independence among metrics/baselines.

Selective coverage, different task digests, missing baseline rows, post-hoc baseline removal or aggregate-only comparison is an automatic FAIL.

`DGC_EXTERNAL_ROUTER_PARETO_SUPPORTED` remains impossible while `bench-release.tar.gz` is not materialized and SHA-256 verified.
