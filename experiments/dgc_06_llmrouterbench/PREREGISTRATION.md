# DGC-06 — Same-Workload LLMRouterBench Performance-Cost Comparison

Date frozen: 2026-08-22
Status: PRE-EXECUTION / BLOCKED_DATA_NOT_MATERIALIZED

## External benchmark authority

Repository: `ynulihao/LLMRouterBench` commit `c77cb0506949d8f959e97967d2fefca0e8ff1b05`.
Dataset: `NPULH/LLMRouterBench/bench-release.tar.gz`.
Published size: `1.28 GB`.
Published SHA-256: `b79f8cde1a6f029c2efa663a3a3b6f7748defb22341fe59f328cebef6648c8f1`.

The benchmark reports 33 models, 21+ datasets, 10 routing algorithms, 400K+ instances and per-instance prompt/prediction/ground-truth/score/token/cost fields. Its performance-cost metric `CostSave` is maximal cost reduction while maintaining Best-Single accuracy. Reported top-router results are a competitive null only; they are not DGC evidence.

## Question

Can a DGC sequential compute-admission policy lie on or improve the same empirical cost-quality Pareto frontier as strong routing baselines (especially Avengers-Pro) when evaluated on the exact same pre-collected query/model/cost table?

## Non-negotiable comparability

- identical query population and train/test split;
- identical model pool and stored model outputs;
- benchmark-provided scores/ground truth only;
- benchmark-recorded per-instance costs, with DGC meta-overhead separately added;
- no provider substitution or updated price normalization inside the primary endpoint;
- same Best-Single reference accuracy and coverage semantics;
- Avengers-Pro / published strong-router result must be reproduced from the materialized bundle before any DGC superiority claim.

## DGC policy boundary

DGC may sequentially purchase additional model outputs only using information available before the next stored model result is revealed. Oracle knowledge of unqueried model scores is forbidden. The exact model-call sequence, calibration split, feature set and stopping estimator must be frozen in a second pre-execution amendment after schema inspection and before benchmark score execution.

## Promotion gate

`DGC_EXTERNAL_ROUTER_PARETO_SUPPORTED` requires preregistered same-workload Pareto non-domination against Avengers-Pro and all reproduced strong baselines, with matched or better quality/coverage and total cost including DGC overhead.

Until the 1.28 GB bundle is materialized and SHA-256 verified, status is `BLOCKED_DATA_NOT_MATERIALIZED`; neither superiority nor inferiority is inferred from published aggregate numbers.
