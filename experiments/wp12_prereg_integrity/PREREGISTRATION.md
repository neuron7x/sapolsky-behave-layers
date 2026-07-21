# PREREGISTRATION — WP12 Preregistration-Integrity Audit

**Committed before the run.** The audit flagged that preregs could be committed with results
(HARKing risk). This machine-verifies, across ALL experiments, that each PREREGISTRATION's first-add
commit is a **strict git ancestor** of the experiment's first result (verdict.json) commit.

## Design (frozen)

For each `experiments/*/PREREGISTRATION*.md`: `prereg_commit` = its first-add commit; map to results
via the artifact `verdict.json`'s `experiment` field; `result_commit` = its first-add commit.
Classify: `STRICT_ANCESTOR` (clean), `SAME_COMMIT_RETROSPECTIVE` (prereg+results together),
`RESULT_BEFORE_PREREG` (integrity violation), `NO_ARTIFACT`. Same-commit is allowed **only** if the
experiment is in the disclosed `RETROSPECTIVE_ALLOWLIST` (matching DEBT_REGISTER + this run's
disclosed meta re-analyses).

## Decision rule (FROZEN)

- **PREREG_INTEGRITY_CLEAN** iff every experiment is `STRICT_ANCESTOR`, `NO_ARTIFACT`, or a
  **disclosed** `SAME_COMMIT_RETROSPECTIVE`. No undisclosed same-commit, no result-before-prereg.
- **PREREG_INTEGRITY_VIOLATION** — any undisclosed same-commit or result-before-prereg.

## Honest note

This gate caught the autonomous rigor run's own batching shortcut (wp9/10/11/13 committed
prereg+results same-commit); those are disclosed in the allowlist rather than hidden. The mechanism
arcs (plasticity, compute, WP6/7/8) are genuine `STRICT_ANCESTOR`. New claim
`CWC-RIGOR7-prereg-integrity`.
