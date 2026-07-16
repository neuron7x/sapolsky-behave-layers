# Experiment Closeout Template

Copy to `artifacts/<exp>/EXPERIMENT_CLOSEOUT.md` when an experiment completes.

## Fields
```
experiment_id:
protocol_version:
preregistration_commit:
execution_commit:
environment_hash:
dataset_hashes:
planned_seeds:
completed_seeds:
excluded_runs:
protocol_deviations:
primary_result:
secondary_results:
failed_controls:
budget_violations:
statistical_verdict:
claim_impact:            # which claim_id(s) this run supports/narrows/refutes
limitations:
artifact_hashes:         # SHA256SUMS
release_eligibility:
```

## Closeout decision (one of)
`ACCEPTED_SUPPORTED · ACCEPTED_NEGATIVE · ACCEPTED_INCONCLUSIVE ·
INVALID_PROTOCOL_DEVIATION · INVALID_DATA_INTEGRITY · INVALID_MEASUREMENT ·
BLOCKED_INSUFFICIENT_POWER`
