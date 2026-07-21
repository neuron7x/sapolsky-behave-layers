# PREREGISTRATION — WP8 Family-Wise Error Meta-Audit

**Committed before the run.** With 16 SUPPORTED claims, several gated on a `δ=0.05` certificate,
an expert reviewer's first multiplicity question is: what is the **family-wise error rate** (the
chance that *at least one* SUPPORTED certificate positive is a false positive)? Untreated, it can
inflate to `1−(1−0.05)^m`. This meta-audit applies family-wise correction and re-certifies the
positives, on top of the proof-complete corrected bound (WP7).

## The family (frozen)

The δ-controlled identifiability certificates whose gate is `G_lo > 0` (a false positive is
statistically possible): `CWC-L4-plasticity` and `CWC-AC1-compute` (the two recomputable from
committed raw seeds). Recovery-/monotonicity-/ceiling-gated positives (L4a/L4b/L4f/L4i/AC2/AC3/AC4)
are reported separately — they pass by margins (recovery 1.000, NULL 0.000) with effectively zero
FPR and are not part of the δ-certificate family.

## Design (frozen)

Recompute `G_lo_corrected` (WP7 proof-complete bound) for each family member at three
correction levels, from **least to most conservative**:
- `δ = 0.05` (uncorrected);
- **Bonferroni over the δ-certificate family** `δ/m_family`;
- **Bonferroni over ALL claims** `δ/29` (ultra-conservative worst case).
Also report **Holm** (step-down) adjusted survival over the family.

## Decision rule (FROZEN)

- **WP8_FWER_CONTROLLED** iff **every** family member has `G_lo_corrected > 0` at the Bonferroni
  family level (and, reported, at the ultra-conservative all-claims level). Then the family-wise
  false-positive rate over the SUPPORTED certificate positives is `≤ 0.05`.
- **WP8_FWER_NARROWS** — some member drops to `G_lo_corrected ≤ 0` under family correction (honest
  narrowing: that positive is not multiplicity-robust).

## Scope

Meta / statistical rigor. Controls family-wise error across the SUPPORTED certificate positives.
New claim `CWC-RIGOR2-fwer`. No new empirical mechanism.
