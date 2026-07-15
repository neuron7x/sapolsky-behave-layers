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
`torch==2.9.1`). GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 3953393664 bytes (~3.68 GiB) VRAM, driver
per `nvidia-smi`. Per Act §1.3, an isolated `.venv-wp1` was created via `uv venv .venv-wp1 --python
3.12` and `uv sync --extra gpu` was invoked to resolve the exact `uv.lock` dependency set. Wheel
downloads (torch CUDA extras total several GiB) may not complete within a single session; any
latency/VRAM/energy number produced outside a venv with confirmed `torch==2.9.1` is recorded with
`environment_match: false` and is **NON-CLAIMABLE**, per the Act's own rule — not silently reported
as if matched.

## Consequences

- Static/analytical code (config, types, FLOP formulas, writer, manifest schema) is fully unit
  tested against whatever torch is available, since these do not depend on the exact pinned
  version's runtime behavior.
- CUDA-timing-precision tests and the real-load overhead gate (Act §4.14, §9) are run against
  actual local CUDA hardware where possible; if bound to the exact `torch==2.9.1` resolution instead
  and that resolution is not complete when this ADR is written, those specific claims are marked
  `ENVIRONMENT_MISMATCH — NON-CLAIMABLE` rather than blocking the rest of WP-1.
- `baseline`/`master` remain byte-identical to upstream `karpathy/nanochat`; all WP-1 work lands on
  `wp1-instrumentation` only.
