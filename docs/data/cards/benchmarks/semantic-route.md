# Benchmark Card — semantic-route

| Field | Value |
|---|---|
| Measured construct | need for a global semantic mechanism vs a local direct path |
| Mechanism necessity | HARD (passive+distractor+negation) requires the semantic path; EASY does not |
| Oracle gap | 99.8% (LCB95 > 0) — identifiable |
| Best-fixed baseline | present (all-direct / all-semantic) |
| **Surface leakage** | **YES** — length/histogram AUROC=1.0, first_token 0.834 (`leakage_probe.py`) |
| Saturation | no |
| Contamination | none (disjoint synthetic seeds) |
| Task balance | 50/50 EASY/HARD |
| Intended scope | routing-causality demonstration under controlled leakage |
| Invalid extrapolations | structure-only routing; real workloads |
| Failure modes | controller may ride surface cues (see CWC-L2a caveat) |
| Version history | 1.0 |

**Note:** because of the surface leakage, this benchmark supports routing-causality
claims only with the leakage caveat. The surface-matched benchmark exists to remove it.
