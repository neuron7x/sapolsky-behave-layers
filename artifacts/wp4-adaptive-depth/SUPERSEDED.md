# ⚠️ SUPERSEDED INTERPRETATION — read before trusting `verdict.json`

The immutable files in this bundle (`verdict.json`, `analysis.json`, `RESULTS.md`,
`raw_runs/`, checksummed by `SHA256SUMS`) are preserved verbatim for provenance and
**must not be edited**. Their *interpretation* has been corrected.

`verdict.json` here still reads `ADAPTIVE_COMPUTE_JENSEN_GAP_CONFIRMED` with
`analysis.compute_matched: true`. **That interpretation is retracted.** See
[`docs/vnv/EPISTEMIC_CORRECTION_WP4_2026-07-19.md`](../../docs/vnv/EPISTEMIC_CORRECTION_WP4_2026-07-19.md).

## What the evidence actually establishes (corrected)

- The observed adaptive−static solved-rate difference equals the empirical tail
  mass `P_sample(m > K)`. This is an **executable algebraic identity of the
  benchmark**, not an independently predicted empirical effect — both sides are
  computed from the same sampled `m` values.
- Compute is **not** exactly matched: adaptive uses `E_sample[m]` hops, static uses
  `round(E_sample[m])` (a 0.095–0.223 hop mismatch by regime). So
  `compute_matched: true` in `analysis.json` overstates parity.
- The adaptive policy receives a **free exact halt oracle**; no learned stopping
  rule, noisy halt signal, or controller cost is validated.

## Corrected claim boundary

- **SUPPORTED_NARROWED** — a unit test of allocation logic + a positive control for
  the identifiability framework. Registry claim: `CWC-L2p-jensen-gap`.
- **NOT TESTED** — compute-equivalent Pareto advantage, learned stopping, noisy/
  expensive halt robustness, real-workload generalization, novelty, independent
  replication.

Canonical status lives in [`claim_registry.json`](../../claim_registry.json)
(`CWC-L2p-jensen-gap` → `SUPPORTED_NARROWED`) and [`SYSTEM.md`](../../SYSTEM.md).
This marker is intentionally **not** listed in `SHA256SUMS` (the frozen manifest is
unchanged); it is a supersession banner, not part of the sealed evidence.
