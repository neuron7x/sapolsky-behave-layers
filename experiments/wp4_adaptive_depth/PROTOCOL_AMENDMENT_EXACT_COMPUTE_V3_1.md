# WP4 Exact-Compute v3.1 — Prospective Protocol Amendment

Status: `INTERNAL_AMENDMENT_FREEZE_REQUIRED_BEFORE_RUN`.

Reason: v3 seeds 100–115 were invalidated because the control budget used
realized holdout `sum(m)`. This amendment was written after viewing the invalid
run, so those seeds are permanently excluded and none of their metrics informs
this design.

## Frozen replacement budget

For distribution weights `w_k`, batch size `B=4096`, and depths `k=1..8`, set

`TOTAL_HOPS_d = round(B * sum(k*w_k)/sum(w_k))`.

This is computed from the protocol-declared distribution, before sampling any
examples. It cannot depend on realized `m`, labels, or outcomes.

Frozen totals:

| Distribution | Total hops |
|---|---:|
| uniform | 18432 |
| easy_skew | 12743 |
| hard_skew | 24121 |
| bimodal | 18432 |
| extreme_easy | 10103 |
| extreme_hard | 26761 |
| mid_peak | 18432 |

## Replacement primary arms

- `input_blind_exact`: floor/ceiling depths randomly permuted, exact frozen total.
- `adaptive_budgeted`: online halt-conditioned allocation under the same frozen
  total; when budget exhausts, unfinished items fail; surplus budget is billed as
  post-convergence no-op hops. It may not inspect `m` directly.

Both arms must report exactly the frozen total or the cell is invalid.

## New untouched data

- Seeds: exactly `200..215`.
- Pilot seeds `0..7` and invalid v3 seeds `100..115` are prohibited.
- Batch size 4096; 32 nested input-blind permutations.
- All other v3 statistical gates, MDE, multiplicity rules, limitations and
  secondary stress grids remain unchanged.

This amendment requires its own commit before implementation and execution.
