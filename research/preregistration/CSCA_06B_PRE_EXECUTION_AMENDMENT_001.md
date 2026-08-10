# CSCA-06B-OP — Pre-execution Amendment 001

**Date:** 2026-08-10  
**Observed scientific data before amendment:** NONE.  
**Trigger:** the first direct CLI invocation terminated during Python import with `ModuleNotFoundError: No module named 'cwc'` before model loading or any prompt/intervention evaluation.

## Change

`experiments/csca_06b_operator_robustness/run.py` now resolves repository root from `__file__` and inserts that root into `sys.path` before repository-local imports.

## Unchanged

All scientific definitions, prompt namespaces, donor kernels, calibration rule, thresholds, cohort definitions, checkpoints, metrics, fail predicates and authority boundaries remain byte-for-byte conceptually unchanged.

This is an execution-hermeticity repair, not a scientific amendment.
