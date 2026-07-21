# WP7 Certificate Hardening — RESULTS (the audit's proof gap, closed)

**Verdict: `WP7_GAP_CLOSED_POSITIVES_ROBUST`.** Preregistration:
`experiments/wp7_certificate_hardening/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp7_certificate_hardening.src.hardening`.

## The flagged proof gap is closed with a proof-complete bound

The audit flagged: the inference certificate's written coverage proof bounds only the
*expectation* of the oracle-term overshoot and allocates the entire deviation budget to the fixed
term, missing the oracle term's concentration — a complete high-probability bound needs `b + 2d`.
The corrected bound (`gap_lower_confidence_bound_corrected`) budgets **both** deviation terms,
union-bounded at `δ/2`:

`G_lo = Ĝ − b − 2·d`,  `b = sd√(2ln|A|)`,  `d = (sd/√|C|)√(2ln(4/δ))`  ⇒  `P(G ≥ G_lo) ≥ 1 − δ`.

## (1) The corrected bound is empirically valid (FPR ≤ δ on every null)

| null family | original FPR | corrected FPR (≤ δ=0.10) |
|---|---|---|
| additive 3×3 | 0.000 | 0.000 |
| additive 4×4 | 0.000 | 0.000 |
| tied 4×4 | 0.000 | 0.000 |
| tied 2×8 | 0.000 | 0.000 |
| tied 6×3 | 0.000 | 0.000 |

Both bounds hold FPR ≤ δ; the corrected one is strictly more conservative (proof-complete).

## (2) Every identifiability positive survives the corrected bound

| claim | `Ĝ` | original `G_lo` | **corrected `G_lo`** |
|---|---|---|---|
| CWC-L4-plasticity (λ=1) | 0.1909 | +0.1108 | **+0.0601** |
| CWC-AC1-compute (λ=0) | 0.6241 | +0.6213 | **+0.6195** |

L4 shrinks (0.111 → 0.060) but stays comfortably positive; AC1 is essentially unchanged (huge
margin). **The identifiability positives are robust to the proof-complete certificate.**

## What this buys — expert-class validity

The sharpest legitimate critique of the theory (a real coverage-proof gap, self-flagged in the
audit) is now closed: the certificate is proof-complete, its coverage is Monte-Carlo-verified
`≤ δ`, and every positive survives it. This is validity by construction, not by assertion.

`CWC-RIGOR1-certificate` is registered **SUPPORTED**. Also closes the "Proof caveat" in
`docs/IDENTIFIABILITY_INFERENCE.md`.

## Scope

Meta / rigor-hardening. Strengthens the validity of existing positives; adds no new empirical
mechanism.
