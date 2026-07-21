# WP8 Family-Wise Error Meta-Audit — RESULTS

**Verdict: `WP8_FWER_CONTROLLED`.** Preregistration:
`experiments/wp8_family_wise_error/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp8_family_wise_error.src.fwer`.

## The positives survive multiplicity correction on top of the proof-complete bound

Applying family-wise correction (Bonferroni + Holm) *simultaneously with* the WP7 proof-complete
corrected bound, the identifiability certificate positives still hold `G_lo > 0`:

| claim | `Ĝ` | uncorrected `G_lo` | Bonferroni (family, δ/2) | Bonferroni (ALL 29, δ/29) |
|---|---|---|---|---|
| CWC-L4-plasticity | 0.1909 | +0.0601 | **+0.0530** | **+0.0292** |
| CWC-AC1-compute | 0.6241 | +0.6195 | **+0.6193** | **+0.6185** |

Holm step-down: both survive. So the **family-wise false-positive rate** over the SUPPORTED
certificate positives is `≤ 0.05` — even in the worst case where *all 29 claims* are treated as one
family (`δ/29 = 0.0017`). The double-hit an expert reviewer applies (proof-complete bound **and**
multiplicity correction) does not overturn the positives.

## What is and isn't in the family

The δ-certificate family is the two `G_lo > 0` gated positives recomputable from committed raw
seeds. The recovery-/ceiling-/monotonicity-gated positives (L4a/L4b/L4f/L4i/AC2/AC3/AC4) are
**excluded** — they pass by margins (recovery 1.000, NULL 0.000; ceiling saturation) with
effectively zero false-positive rate, so multiplicity correction is not the relevant control for
them. This is stated to avoid inflating the apparent family and to keep the correction honest.

## Consequence — expert-class statistical validity

Together with WP7 (proof-complete coverage) this closes the two sharpest legitimate statistical
critiques of the ladder: **(1)** the certificate is proof-complete and FPR-verified, and **(2)** the
positives are robust to family-wise multiplicity correction. `CWC-RIGOR2-fwer` is registered
**SUPPORTED**.

## Scope

Meta / statistical rigor. Family-wise error control across the SUPPORTED certificate positives.
