# Validation Record

Scientific validation per claim (construct validity, identifiability, causality,
controls, statistics, leakage). Current at commit d920f79+.

| Claim | Validation basis | Verdict |
|---|---|---|
| CWC-L0-measurement | determinism + mutation + coverage gates | SUPPORTED |
| CWC-L1-identifiability | oracle gap 99.8%, LCB95>0 | SUPPORTED |
| CWC-L2-routing-causality | controls + interventions; narrowed by review | SUPPORTED_NARROWED |
| CWC-L2a-e2e-reinforce | 8 seeds, paired diff UB −0.465, AUROC 1.0 | SUPPORTED (binding budget; surface caveat) |
| CWC-L2b-route-decision-cost | 4 arms × 8 seeds chance; supervised probe chance | SUPPORTED |
| CWC-L2p-jensen-gap | gap=P(m>K) to 0.0000, 8×4, beats random | SUPPORTED |
| CWC-L2c-e2e-straightthrough | collapse; superseded by L2a | NOT_SUPPORTED |
| CWC-L3-rcfr | ties prior art | NOT_SUPPORTED |
| CWC-L4-plasticity | non-identifiable unbudgeted | NOT_TESTED |
| CWC-fractal | null not rejected (archival) | NOT_SUPPORTED |
| CWC-L7-pareto / CWC-L8-replication | not run / not self-certifiable | NOT_TESTED |

No claim exceeds its validation basis; the two `NOT_TESTED` frontier claims are
explicitly cloud/independent-operator blocked.
