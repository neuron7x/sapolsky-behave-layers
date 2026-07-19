# WP4 Exact-Compute v3 — Invalidated Run

Final status: **`INVALID_PROTOCOL_DEVIATION`**.

Seeds 100–115 were executed after protocol commit `6245a6d`, but the
implementation supplied the input-blind control with `sum(m)` from the realized
confirmatory batch. The frozen protocol permits only a globally preregistered
budget and forbids access to realized holdout difficulty, even in aggregate.

The generated `analysis.json` is retained for audit but its provisional
`SUPPORTED_NARROWED_INTERNAL` verdict is void. None of its effects, intervals or
p-values may support a claim or power a successor confirmation.
