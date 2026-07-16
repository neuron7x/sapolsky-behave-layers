# Benchmark Card — surface-matched-duplicate

| Field | Value |
|---|---|
| Measured construct | can a controller route on a purely STRUCTURAL difficulty signal? |
| Mechanism necessity | FAR needs the global path; NEAR is local-solvable |
| Oracle gap | present (global solves all; local fails FAR) — sanity: all_global≈0.002, all_local≈1.86 |
| Best-fixed baseline | all-global / all-local |
| **Surface leakage** | **NO by construction** — identical length, first token, token histogram; probes ~0.5 |
| Saturation | no |
| Contamination | none |
| Task balance | 50/50 NEAR/FAR |
| Intended scope | isolate route-decision cost (structure not cheaply computable) |
| Invalid extrapolations | tasks where difficulty IS cheaply computable |
| Failure modes | none identified; verdict ROUTE_DECISION_IS_THE_COMPUTATION |
| Version history | 1.0 |

**Result:** neither a cheap nor an attention controller routes above chance even under
direct supervision → the route decision costs ~the expensive computation.
