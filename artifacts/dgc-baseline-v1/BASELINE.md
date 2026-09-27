# DGC Baseline v1

**Status:** `FROZEN_PARTIAL / FAIL_CLOSED`  
**Purpose:** ACT-00 pre-DGC authority snapshot. This file records what is verified and explicitly refuses to treat unavailable execution as a green gate.

## Source authority

- repository: `neuron7x/sapolsky-behave-layers`
- branch: `main`
- commit: `08c03b1e5a217c05c263ac1fd20bebb9365aac2a`
- tree: `d72c2e6ce7113236475dc699ee47207cc3b5504f`
- commit message: `Prepare canonical public release`
- uploaded baseline archive comment: `08c03b1e5a217c05c263ac1fd20bebb9365aac2a`
- `uv.lock` SHA-256: `8fa16613c12a5d9f40f53e22e24610c05165b90c4c38bbed0f0b7975404d0669`

The commit/tree pair was read from the GitHub git-commit object. File hashes were computed from the uploaded archive whose archive comment equals the same commit.

## Baseline execution evidence

On the pristine uploaded main snapshot:

- `python scripts/architecture_gate.py` -> PASS;
- `python -m pytest -q tests/test_engineering_assurance.py::test_architecture_contract_matches_real_import_graph` -> 1 passed;
- engineering-assurance subgates executed directly through `make ... PY=python`: architecture PASS, hermeticity PASS, complexity PASS, dependency-integrity self-test PASS (5/5 injected attacks killed), dependency-integrity PASS, SBOM PASS, inference-integrity PASS, assurance-attack PASS (5/5 injected attacks killed);
- final `assurance_report.py` did not execute because the uploaded GitHub archive intentionally contains no `.git` object database and the report requires `git rev-parse HEAD` / `HEAD^{tree}`.

Therefore ACT-00 acceptance condition **"all existing gates green" is not asserted**. The baseline identity is frozen, but canonical full-gate execution remains unresolved rather than being inferred from partial evidence.

## Immutability rule

DGC work must not rewrite historical baseline results or old scientific claims. Any later baseline completion must add evidence bound to the same commit/tree or create a new baseline version; it must not silently change this record.
