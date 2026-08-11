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
Python 3.10 is selected by `.python-version`. The frozen runtime lock resolves PyTorch 2.13.0,
with CPU (`2.13.0+cpu`) or CUDA 13.0 (`2.13.0+cu130`) selected by the uv extra.
Verification-only tooling is separately exact-pinned in `cwc-requirements-dev.txt`.

## Install & smoke test
```bash
uv sync --frozen --extra cpu
make -f Makefile.cwc install-dev
make -f Makefile.cwc experiment-tests        # discovers experiment test directories dynamically
make -f Makefile.cwc verify-evidence         # checks every committed SHA256SUMS bundle dynamically
```

## Full reproduction
```bash
make -f Makefile.cwc verify                  # lint+types+tests+coverage+mutation+experiments
make -f Makefile.cwc reproduce-primary       # primary result end-to-end
```
Expected outputs, tolerances and per-result commands: `RESULT_TO_SCRIPT_MATRIX.csv`.
Expected runtime/cost: `EXPECTED_RUNTIME_HARDWARE_AND_COST.md`.

## License / citation
MIT (`LICENSE`); cite via `CITATION.cff`. Archival identifier: pending public release
(GitHub org currently suspended — see `SYSTEM.md`).
