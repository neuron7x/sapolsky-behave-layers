# WP-2 Routing v1 — CLAIM MATRIX

| Claim | Required evidence | Available evidence | Status |
|---|---|---|---|
| Instrumentation is measurement-valid | WP-1 L2 overhead gate | PASS (confirmatory N=2000, `../wp1-release/`) | VERIFIED |
| Compute parity across K-configs ≤ 1% | FLOP accounting all 4 K-configs | 0.03% (controller vs backbone) | VERIFIED |
| Hard budget never exceeded | eval budget-violation counters | 0 across all K-configs/seeds | VERIFIED |
| Learned > random (per-sequence) | paired bootstrap CI | Δ=−0.0162, CI [−0.020,−0.014] < 0 | SUPPORTED (pilot) |
| Learned > frozen | paired bootstrap CI | Δ=+0.0013, CI straddles 0 | NOT_SUPPORTED |
| Learned > fixed-depth | paired bootstrap CI | Δ=−0.0005, CI straddles 0 | NOT_SUPPORTED |
| Learned forms adaptive non-collapsed policy | per-layer utilization | [1,1,1,1,0,0,0,0] constant = collapse | NOT_SUPPORTED |
| H_CWC: learned adaptive allocation beats static | learned > all static controls | fails vs frozen & fixed-depth | NOT_SUPPORTED |
| Pareto advantage of learned routing | dominance on (quality, compute) | learned = fixed-depth = frozen at K=4 | NOT_SUPPORTED |
| Energy comparison | validated telemetry | INSTRUMENT_INVALID upstream | NOT_TESTED |
| ≥5-seed statistical claim | ≥5 seeds | 3-seed pilot only | NOT_TESTED (PILOT) |

## Prohibited wording (unearned by this evidence)
- "CWC learns to allocate compute" — the controller collapsed to a constant
  policy; it did not learn adaptive allocation.
- "learned routing is efficient / Pareto-superior" — it matches, does not beat,
  static controls at equal compute.
- "adaptive compute helps" — not on this task at this budget.

## Earned wording
- "A fixed 4-of-8 block selection matches the full 8-block model on this task."
- "Consistent block selection beats random per-sequence selection."
- "The learned controller collapsed to a static first-K policy; learned
  adaptive routing showed no advantage over static allocation at this scale."
