# Reproduce WP-2 routing v1

Exact steps to regenerate every artifact in this bundle from the repository.

## Environment
- Repo commit: see `../wp1-release/repository_manifest.json` (branch
  `wp1-instrumentation`, baseline `92d63d4e`).
- Python 3.10.20, pinned `.venv` from committed `uv.lock`.
- torch 2.9.1+cu128, CUDA GPU (results below are RTX 3050 Laptop, 4 GiB).
- No external dataset — the task is synthetic and seeded.

## 1. Gates (must pass before any run — Act §13)
```bash
make -f Makefile.cwc verify
PYTHONPATH=. .venv/bin/python -m pytest experiments/wp2_routing_v1/tests/ -q
```

## 2. Multi-seed experiment
```bash
# pilot (3 seeds, claimable=no)
PYTHONPATH=. .venv/bin/python experiments/wp2_routing_v1/src/runner.py \
    --seeds 0 1 2 --out artifacts/wp2-routing-v1/raw_runs
# claim tier (>=5 seeds) — same command, more seeds:
PYTHONPATH=. .venv/bin/python experiments/wp2_routing_v1/src/runner.py \
    --seeds 0 1 2 3 4 --out artifacts/wp2-routing-v1/raw_runs
```
Each `(config, seed)` writes `raw_runs/<config>/seed<N>.json` with quality,
compute, systems and routing metrics. Fixed hyperparameters live in
`../../experiments/wp2_routing_v1/protocol.yaml`.

## 3. Statistics + verdict (Act §11/§16)
```bash
PYTHONPATH=. .venv/bin/python experiments/wp2_routing_v1/src/analyze.py \
    --runs artifacts/wp2-routing-v1/raw_runs \
    --out artifacts/wp2-routing-v1/statistics
```
Writes `statistics/analysis.json` with paired bootstrap CIs and the
machine-readable verdict. Bootstrap is deterministic (fixed LCG seed).

## Determinism notes
- Same seed ⇒ same backbone init AND same training data order across all 5
  configs (the seed drives both `torch.manual_seed` and the data
  `torch.Generator`).
- Validation set is fixed (`Generator(999_999)`), identical for every config
  and seed.
- Eval routing is deterministic (argmax top-K; random config uses a fixed
  per-batch RNG).
