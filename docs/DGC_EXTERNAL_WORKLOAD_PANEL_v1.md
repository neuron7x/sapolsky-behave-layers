# DGC External Workload Panel v1

Status: `SOURCE_IDENTITIES_FROZEN / TASK_BYTES_NOT_YET_MATERIALIZED`
Date: 2026-08-22

This panel implements the product protocol requirement for at least two independent external software-agent workload families. It freezes source identities only. It does **not** claim that the evaluation harness is frozen until the task bytes, scorer/runtime assets and environment images are materialized and hashed into the DGC evidence bundle.

## Family A — SWE-bench Verified

- upstream repository: `SWE-bench/SWE-bench`
- frozen repository commit: `7a21e05772954cc81471ae19d56f436cecf43c54`
- dataset identity: `SWE-bench/SWE-bench_Verified`
- expected instances: `500`
- task semantics: human-filtered real GitHub software issues with executable repository tests
- DGC role: repository issue diagnosis/patch workload

## Family B — Terminal-Bench 2.1

- upstream repository: `harbor-framework/terminal-bench-2-1`
- frozen repository commit: `7131e4375048a0e408a8fb404b5f499d726b695b`
- dataset identity: `terminal-bench/terminal-bench-2-1`
- expected tasks: `89`
- task semantics: independent end-to-end terminal-agent tasks in containerized environments
- DGC role: broader engineering/terminal workload with different task generator, harness semantics and failure modes from SWE-bench

Terminal-Bench 2.1 is selected instead of 2.0 because the 2026-05-06 release specifically repaired a substantial set of 2.0 task issues and introduced stronger continuous validation.

## Required materialization gate

Before `harness_frozen=true`, create for each family:

1. exact task manifest with stable task IDs;
2. byte-level dataset/archive digests;
3. scorer/evaluator commit digest;
4. environment/container digest per task or canonical environment set;
5. oracle/environment sanity results where the benchmark provides them;
6. contamination/exclusion declaration;
7. task count reconciliation against the frozen expected count.

If any expected task is missing, mutated after freeze, or cannot run in the declared environment, the product comparison is not authorized until the discrepancy is preregistered and resolved.

## Comparison invariant

Within each family, baseline and DGC runs must share identical task bytes, model pool, prompts/system policy, tools, environment, budgets, scorer, pricing snapshot and statistical plan. Only governance policy may differ.

## Boundary

The two source identities are now frozen. `external_real_workload_supported=false` remains mandatory until DGC is actually executed on these materialized workloads under the frozen controlled harness and passes preregistered quality/regret/coverage/cost gates.
