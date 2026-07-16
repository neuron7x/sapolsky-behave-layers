# Third-Party Notices

CWC is released under the MIT License (`LICENSE`). It incorporates and depends on
third-party components, each under its own license. This file is advisory; the
authoritative, machine-readable dependency set is `uv.lock` / `pyproject.toml`.

## Upstream baseline
- **nanochat** — Andrej Karpathy. CWC is built on top of nanochat; the upstream
  baseline commit is recorded pristine in `artifacts/base-commit.txt` and the
  upstream README is preserved at `docs/upstream/NANOCHAT_README.md`. See upstream
  repository for its license.

## Primary runtime dependencies (see `uv.lock` for exact pins & hashes)
| Component | Role | License (typical) |
|---|---|---|
| PyTorch (`torch`) | tensor / autograd / CUDA | BSD-3-Clause |
| NumPy (`numpy`) | numerics | BSD-3-Clause |
| tiktoken, rustbpe | tokenization | MIT |
| pyarrow | data I/O | Apache-2.0 |
| psutil, filelock, python-dotenv | runtime utilities | BSD / MIT |
| kernels | GPU kernels | see package |
| wandb, matplotlib, ipykernel | tooling / plots (dev) | MIT / PSF |

## Development / verification tooling
| Component | Role | License |
|---|---|---|
| pytest, hypothesis | testing / property tests | MIT / MPL-2.0 |
| ruff | lint | MIT |
| mypy | type checking | MIT |
| uv | environment resolver | Apache-2.0 / MIT |

Each dependency's full license text ships with that package in the resolved
environment (`.venv/`) and is reconstructible via `uv sync --frozen`. If any license
here is inaccurate, `uv.lock` is authoritative and this file should be corrected to
match it (tracked by the release-integrity gate).
