# DGC CI Execution Blocker — 2026-08-22

Historical incident status: **CI_EXECUTION_UNAVAILABLE** on the recorded jobs.
For later CI evidence keyed to exact commits, see the
[verification execution state](DGC_EVIDENCE_CLOSURE_EXECUTOR_v1.md#19-verification-execution-state).

## Observed facts

For PR #9 head-family runs, GitHub creates workflow runs/jobs but terminates them before any declared job step executes.

Representative incident evidence:

- workflow: `cwc-quality`, run `32557986090`;
- job: `96995108157`;
- job conclusion: `failure`;
- job steps returned by GitHub API: empty list / `steps=null`;
- job log URL: absent; log download returns `BlobNotFound`;
- workflow artifacts: none;
- public run page resolves to `DisabledError`.

The same pre-step pattern has occurred across `cwc-quality`, `cwc-full-pr-gate`, `cwc-doc-gates`, `pr-audit`, and `codeql` and reproduced across multiple DGC branch heads.

## Classification

This evidence classifies those jobs as unavailable before repository test
execution. A code verdict requires repository steps and their results.

The incident classification carries no PASS for the affected jobs.

## Recovery procedure for this failure mode

Restore GitHub Actions execution authority for the repository/account (repository Actions enablement, account/billing/plan or policy state as applicable), then rerun the existing workflows without weakening any gate. The available connector does not expose repository Actions-enablement/billing policy mutation, so this cannot be repaired honestly from the code branch itself.

## Local substitute boundary

Local pytest/architecture/assurance/compile gates may diagnose code, but they do not replace merge-grade GitHub CI authority. `ruff` and `mypy` remain UNKNOWN where their pinned executables are unavailable.
