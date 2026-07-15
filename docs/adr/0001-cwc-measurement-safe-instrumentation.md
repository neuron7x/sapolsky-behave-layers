# ADR-0001: CWC WP-1 Measurement-Safe Instrumentation

Status: accepted

## Context

CWC-NANOCHAT-WP1-INSTRUMENTATION-ACT v1.0.0 requires a metrologically sound measurement layer
before any routing, memory or plasticity mechanism is added to the pinned nanochat baseline
(`92d63d4e8bb4df75c3b71618f31ddde2378b2bcd`, branch `baseline`, tag `wp0-fixation-2026-07-16`).
Without it, a future WP-3 routing result cannot be causally attributed to routing rather than to
measurement artifacts — exactly the failure mode `moe3`'s own MFU regression (46%→35%) would have
been invisible without nanochat's pre-existing MFU telemetry.

## Decision

Build `cwc/instrumentation/` as an always-on-lightweight-core / sampled-audit-tool two-tier system
(Act §2.1), defaulting to `InstrumentationMode.OFF` (true no-op — no CUDA events, no NVML import, no
files, no threads). `COUNTERS` mode is safe for production benchmark use; `TRACE` and `AUDIT` are
never used for final latency/energy claims (Act §2.2, §4.14).

## Environment fixation

Local system Python: 3.12.3. Local system torch: `2.12.1+cu130` (does not match nanochat's pinned
`torch==2.9.1`) — this remains true for the system interpreter and is why `environment_match` exists
as a manifest field at all.

Per Act §1.3, `uv sync --extra gpu --group dev` was run against the project's own `uv.lock` (not the
manually-created `.venv-wp1`, which `uv sync` does not target by default — it resolves into the
project-standard `.venv`). This completed successfully: `.venv/bin/python` resolves `torch==2.9.1+cu128`
exactly, `torch.cuda.is_available()` is `True`, and the full test suite (nanochat's own 58 pre-existing
tests plus 86 new WP-1 tests) passes there — 144 passed, 2 skipped (the 2 skips are `pynvml`-dependent
GPU energy tests; `pynvml` is not a nanochat dependency and its absence is itself the correct
graceful-degradation path the Act requires, not a failure). GPU: NVIDIA GeForce RTX 3050 Laptop GPU,
3953393664 bytes (~3.68 GiB) VRAM.

**Result: environment mismatch is resolved.** Latency/VRAM/energy/FLOP numbers produced via
`.venv/bin/python` in this repository are measured under the exact pinned dependency set and are not
subject to the `ENVIRONMENT_MISMATCH — NON-CLAIMABLE` flag. Numbers produced via the system
interpreter (`python3`, torch 2.12.1) remain flagged accordingly if ever mixed in.

## Consequences

- All WP-1 tests, including CUDA-timing-precision and energy-backend tests, are run and pass against
  the exact pinned environment (`.venv/bin/python`), not just against whatever torch happened to be
  available system-wide.
- The real-load overhead gate (Act §4.14, §9) is executed under this same exact environment, so its
  result is claimable rather than environment-mismatch-flagged.
- `baseline`/`master` remain byte-identical to upstream `karpathy/nanochat`; all WP-1 work — including
  the `.venv` created by `uv sync` — lands on `wp1-instrumentation` only. `.venv/` and `.venv-wp1/`
  are git-ignored per nanochat's existing `.gitignore` and are not part of any committed tree.
