# Verification Record

**Commit:** d920f79 (and successors). **Environment:** Python 3.10.20, PyTorch
2.9.1+cu128, RTX 3050 4GiB, uv-frozen.

| Check | Result |
|---|---|
| ruff (include-allowlist) | PASS |
| mypy --strict (cwc/ + scripts) | PASS |
| unit + property tests | PASS |
| mutation gate (curated) | 12/12 killed |
| determinism tests | PASS |
| experiment tests (`make experiment-tests`) | 69 passed |
| evidence checksums (`verify-evidence`) | 11 bundles OK |
| doc-status gate (`scripts/doc_status_gate.py`) | see DOC-GATE output |

This record supersedes the stale Cognitive Weave Kernel validation report in
`docs/vision/VALIDATION_REPORT.md`, which describes a different artifact and environment
(Python 3.12 / PyTorch 2.13) and is retained only as historical context.
