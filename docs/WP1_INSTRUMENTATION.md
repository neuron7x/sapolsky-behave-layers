# CWC WP-1 Instrumentation

Implements `CWC_NANOCHAT_WP1_INSTRUMENTATION_ACT_v1.0.0` (`/home/neuro7/Downloads/
CWC_Nanochat_WP1_Claude_Code_Act_v1.0.0/cwc-wp1-claude-code-act`, SHA256-verified
before implementation). Baseline commit `92d63d4e8bb4df75c3b71618f31ddde2378b2bcd`
(branch `baseline`, tag `wp0-fixation-2026-07-16`) untouched; all work on
`wp1-instrumentation`.

## What this is

A measurement layer for nanochat, built to be metrologically trustworthy before
any CWC routing/memory/plasticity mechanism is added: `cwc/instrumentation/`
(config, types, noop, clock, event_buffer, run_meter, vram, flops, energy,
routing, writer, manifest, audit) plus four scripts and 100+ tests.

## Two-tier design (Act §2.1)

- **Always-on lightweight core**: `RunMeter` (deferred-synchronization CUDA
  event timing + CPU wall clock), `VRAMMeter` (allocator peak stats, never
  `empty_cache()`), `FlopLedger` (analytical, not profiler-based), `EnergySampler`
  (NVML total-energy delta → power-sampling → unavailable, never TDP),
  `RoutingCounters` (measurement-ready, no router implemented), `Writer`
  (buffered JSONL + atomic JSON + SHA256SUMS).
- **Sampled/isolated audit tools**: `audit.py`'s `torch.profiler` wrapper,
  roofline report, MoE-CAP schema placeholders — never used in a claim run
  (`claim_run: false` is structural, not a convention).

`InstrumentationMode.OFF` is a true no-op: no CUDA events, no NVML import, no
files, no threads (`noop.py`'s `Null*` classes; verified in
`test_instrumentation_noop.py` and the OFF/COUNTERS loss-identity check in
`test_instrumentation_integration.py`).

## Environment fixation (Act §1.3) — resolved

Local system Python/torch (`3.12.3` / `2.12.1+cu130`) does not match nanochat's
pin. `uv sync --extra gpu --group dev` against nanochat's own `uv.lock`
resolved the exact pin (`torch==2.9.1+cu128`) into `.venv/` (not the
manually-created `.venv-wp1/`, which `uv sync` does not target by default and
which was removed once this was discovered). **144→164 tests pass there**
(nanochat's own 58 pre-existing tests + all new WP-1 tests), including real
CUDA event timing, real GPU VRAM allocation, real NVML power sampling, and a
real nanochat `GPT` forward+backward+loss-identity check between OFF and
COUNTERS modes (Gate B). 2 skips are `pynvml`-specific — `pynvml` is not a
nanochat dependency, and its absence exercising the graceful-degradation path
correctly is not a failure.

`environment_match` compares PEP 440 release segments only (`"2.9.1+cu128"`
matches expected `"2.9.1"` — the `+cu128` is CUDA build metadata). This bug
(exact-string comparison originally reported `environment_match: false` for a
build that does match) was caught by running the real smoke test on real
hardware, not by the unit tests alone — a concrete instance of why Act §9's
real-load verification matters beyond unit coverage.

## FLOP ledger agreement (Act §5.4)

`nanochat.gpt.GPT.estimate_flops()` returns forward+backward FLOPs per token
as `6 * num_matmul_params() + attn_flops` (PaLM-paper attention approximation,
no causal halving). This ledger's dense-matmul-only forward portion
(`2 * num_matmul_params()` per token, matching convention) agrees with
nanochat's own estimator within a documented tolerance (ratio 0.85–1.15,
verified in `test_nanochat_estimator_agreement_on_dense_matmul_portion` — the
small gap is nanochat's per-layer value-embedding gate and resid/x0 scalar
lambdas, which this ledger does not model). Separately, `test_instrumentation_audit.py`
and `scripts/instrumentation_audit.py` show **exact agreement (0.0% error)**
between this ledger's analytical FLOPs and `torch.profiler`'s own
`with_flops=True` output for a plain dense matmul, once the analytical count
is scaled to the same number of profiled steps (a real bug in the diagnostic
script — comparing one step's analytical count to ten profiled steps' summed
count — was caught by actually running it and fixed).

## Script integration (Act §5)

- **`scripts/base_train.py`**: `--instrumentation-mode/output/run-id/energy/
  sample-rate-hz/trace-every/window-steps`, default `off`. Wraps the existing
  training-step block in a `RunMeter` scope reusing nanochat's own
  `synchronize()`/`t0`/`t1` (no added synchronization). Verified end-to-end on
  real hardware through manifest/config-writing up to nanochat's own
  pre-existing tokenizer-cache requirement (`FileNotFoundError` for
  `~/.cache/nanochat/tokenizer/tokenizer.pkl` — not caused by this change; no
  trained tokenizer exists in this environment). `manifest.json` from a real
  `--instrumentation-mode=counters` run shows correct git commit/branch/dirty
  state, correct device/environment info, `environment_match: true`.
- **`scripts/infer_bench.py`**: `--instrumentation-mode/energy`, additive
  nested `cwc_instrumentation` payload field (TTLT, TPOT p50/p95/p99, peak VRAM
  reserved, joules/request, joules/token, FLOP ledger); every existing
  top-level field is unchanged and the "last stdout line is valid JSON"
  contract holds. **Not runtime-verified** beyond syntax check and `--help` —
  `infer_bench.py` needs a trained checkpoint via `load_model()`, and none
  exists in this environment (no `tok_train.py`/`base_train.py` run has
  completed here). This is a known, disclosed gap, not a silent one.

## Overhead qualification (Act §4.14, §9) — **BLOCKED_BY_MEASUREMENT_OVERHEAD**

`scripts/instrumentation_overhead.py`: paired alternating OFF→COUNTERS→
COUNTERS→OFF, 5 cycles, real nanochat `GPT` forward+backward+optimizer step,
bootstrap 95% CI. Two real bugs were found and fixed only by actually running
this end-to-end (not caught by unit tests): (1) `_timed_steps` resolved the
meter internally and discarded records, so a second `resolve()` call by the
caller silently returned empty — `gpu_kernel_ms` read back as zero for every
record; (2) the GPU-specific sub-gate compared a single one-shot bare-vs-pooled
measurement rather than averaging across all cycles, and gave contradictory
results between runs (+2.2% one run, −0.76% the next) purely from that
noise — fixed by moving it inside the cycle loop.

**Honest result, 3 independent runs, largest model this RTX 3050 (3.68 GiB)
can run without OOM** (depth=12, n_embd=768, ~50 ms/step — nanochat's own
default depth=20/n_embd=1280 was tried and OOMs on this GPU):

| Run | E2E relative overhead (median) | E2E CI upper | GPU-specific overhead |
|---|---|---|---|
| 1 | 0.89% | 1.14% | −0.76% |
| 2 | 0.65% | 2.25%* | 2.22%* |
| 3 (canonical, saved) | 1.03% | 1.44% | 0.58% |

\* run 2 predates the cycle-averaging fix to the GPU sub-gate; its GPU number
is the noise-dominated single-shot measurement described above and is not
trusted — included for the record, not as evidence.

At toy scale (depth=6, n_embd=384, ~11 ms/step) overhead is clearly and
repeatably above threshold (~2.2%), confirming the effect is a roughly fixed
per-step Python-level cost (event-pool acquisition, dataclass construction,
context-manager entry/exit) that matters less as step duration grows. The
**E2E CI-based criterion passes in all 3 runs**; the **stricter point-estimate
criterion (≤1.0%) passes 2 of 3** — right at the noise floor, not decisively
clear. The canonical run is saved at
`artifacts/instrumentation/overhead_report_canonical_run.json`.

**Verdict:** this is reported as `BLOCKED_BY_MEASUREMENT_OVERHEAD`, not rounded
up to a pass, per the Act's own fail-closed instruction (§9, §12) — re-running
until a passing sample appears would be exactly the kind of cherry-picking the
whole CWC evidence discipline exists to prevent. What would resolve this
honestly: (a) testing at nanochat's actual default scale (depth=20) on
hardware with enough VRAM, where the fixed per-step overhead would be an even
smaller fraction of a longer step; (b) more cycles for a tighter CI; (c) an
isolated GPU with no other process contending for it (this RTX 3050 is a
shared laptop GPU, and `nvidia-smi` showed an anomalous power reading at
session start suggesting some background load or driver quirk, a plausible
contributor to run-to-run noise at this fine a threshold).

## Known limitations

- `infer_bench.py` integration is code-complete but not runtime-verified (no
  trained checkpoint available in this environment).
- The overhead gate is measured on the largest model this GPU's 3.68 GiB VRAM
  supports (depth=12), not nanochat's own default (depth=20) — VRAM-bound, not
  a choice.
- `RunMeter`'s CPU-only path (no CUDA, `enable_cuda_events=False`) has real
  test coverage via CPU-mode integration tests but the dedicated
  `test_instrumentation_cuda_events.py` module is marked `@pytest.mark.cuda`
  and would be entirely skipped on a CPU-only host — acceptable per Act §8.2
  ("Skipped entirely if CUDA is unavailable"), but worth knowing if this
  package is ever exercised on a CPU-only CI runner.
- `compile_state` in the manifest is hardcoded `"unknown"` — `torch.compile`
  interaction with this instrumentation is untested (nanochat's own scripts
  use `torch.compile` in places this integration does not yet introspect).

## Verify

```bash
python -m compileall cwc scripts tests
pytest -q                              # via .venv/bin/python: 164 passed, 2 skipped
pytest -q -m "not cuda"
pytest -q -m cuda
python -m scripts.instrumentation_smoke --device cpu   # SMOKE PASS
python -m scripts.instrumentation_smoke --device cuda  # SMOKE PASS
python -m scripts.instrumentation_overhead --cycles 5 --warmup-steps 20 --measurement-steps 100
python -m scripts.instrumentation_audit --steps 10
python -m scripts.export_cwc_instrumentation_bundle --input artifacts/instrumentation/<run_id>
```
