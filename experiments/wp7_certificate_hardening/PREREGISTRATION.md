# PREREGISTRATION — WP7 Certificate Hardening (close the audit's proof gap)

**Committed before the run.** The 4-axis audit flagged a real proof gap in the inference
certificate (`docs/IDENTIFIABILITY_INFERENCE.md`): the written coverage proof bounds only the
*expectation* of the oracle-term overshoot and allocates the whole deviation budget to the fixed
term, missing the oracle term's concentration — a complete high-probability bound needs ~`b + 2d`,
not `b + d`. This closes the gap to expert-class validity: implement the **proof-complete**
corrected bound, empirically verify its coverage, and re-certify every identifiability positive
under it.

## Design (frozen)

- **Corrected bound** (`gap_lower_confidence_bound_corrected`):
  `G_lo = Ĝ − b − 2·deviation_bound(sd, |C|, δ/2)`, budgeting both the oracle-term and fixed-term
  deviations, union-bounded at `δ/2` each ⇒ `P(G ≥ G_lo) ≥ 1 − δ`. Strictly more conservative.
- **(1) Coverage Monte-Carlo:** for 5 null families (additive `G=0` and least-favorable ties,
  sizes 2×8, 4×4, 6×3, …), 4000 trials each at `sd=0.15, δ=0.10`: the corrected bound's empirical
  FPR must be `≤ δ`.
- **(2) Re-certification:** recompute `G_lo_corrected` for the certificate-based positives from
  their committed raw seeds — `CWC-L4-plasticity` (confirmatory, λ=1) and `CWC-AC1-compute` (λ=0).

## Decision rule (FROZEN)

- **WP7_GAP_CLOSED_POSITIVES_ROBUST** iff the corrected bound's FPR `≤ δ` on **all** null families
  AND **every** re-certified positive has `G_lo_corrected > 0`. The proof gap is closed and the
  positives are robust to the corrected, provably-valid certificate.
- **WP7_CORRECTED_BOUND_INVALID** — corrected FPR `> δ` on some null (the correction is wrong).
- **WP7_POSITIVE_DID_NOT_SURVIVE** — a positive drops to `G_lo_corrected ≤ 0` (honest narrowing).

## Scope

Meta / rigor-hardening (tier: analysis). Elevates the inference certificate to a proof-complete,
empirically-validated bound and re-certifies the positives. New claim `CWC-RIGOR1-certificate`.
Does not add a new empirical mechanism; it strengthens the validity of the existing ones.
