# CWC Artifact README (reviewer-facing)

## Inventory
Source (`cwc/`, `experiments/`, `scripts/`), evidence (`artifacts/`), containers
(`containers/`), schemas (`schemas/`), docs (`docs/`). Entry point: `SYSTEM.md`.

## Supported claims
See `claim_registry.json` (machine-readable) and `docs/vnv/VALIDATION_RECORD.md`.

## Unsupported / prohibited claims
Scale Pareto, energy efficiency, autonomous routing, independent replication,
deployment-readiness — see README §"What CWC does NOT claim".

## Hardware / software
Python 3.11 is selected by `.python-version`. The frozen runtime lock resolves PyTorch 2.13.0,
with CPU (`2.13.0+cpu`) or CUDA 13.0 (`2.13.0+cu130`) selected by the uv extra.
The hosted path installs verification tooling from the hash-pinned
[`requirements/cwc-dev.lock`](../../requirements/cwc-dev.lock).

Python 3.11 is required by the patched filelock, Pillow and Tornado releases.
The isolated, pure-Python P19 external verifier retains its versioned CPython 3.10
contract; its historical receipts and scientific evidence are not migrated.

## Install & smoke test
```bash
uv sync --frozen --extra cpu
make -f Makefile.cwc install-dev
make -f Makefile.cwc experiment-tests        # discovers experiment test directories dynamically
make -f Makefile.cwc verify-evidence         # checks discovered manifests under artifacts/
```

## Full reproduction
```bash
make -f Makefile.cwc verify                  # lint+types+tests+coverage+mutation+experiments
make -f Makefile.cwc reproduce-primary       # primary result end-to-end
```
Expected outputs, tolerances and per-result commands: `RESULT_TO_SCRIPT_MATRIX.csv`.
Expected runtime/cost: `EXPECTED_RUNTIME_HARDWARE_AND_COST.md`.

## License / citation
Use the [repository license](../../LICENSE) and [citation record](../../CITATION.cff).
Cite the exact public commit. Use the [test and CI reference](../vnv/CWC_TEST_AND_CI_REFERENCE.md)
for the tested checkout and artifact digest of a measured result. The persistent
archival release remains open.
