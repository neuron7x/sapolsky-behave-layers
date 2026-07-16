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
Python 3.10.20, PyTorch 2.9.1+cu128, RTX 3050 4GiB (or CPU). Environment from `uv.lock`.

## Install & smoke test
```bash
uv sync --frozen
make -f Makefile.cwc experiment-tests        # 69 tests, ~5 s
make -f Makefile.cwc verify-evidence         # 11 bundles checksum-OK
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
