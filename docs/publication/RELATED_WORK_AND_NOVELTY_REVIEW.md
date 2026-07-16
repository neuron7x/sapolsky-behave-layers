# Related Work and Novelty Review

> **Search-completeness disclosure.** This is a *working* review of the nearest prior art
> actually relevant to the current claims, not a completed systematic survey. A full
> systematic search (databases, dates, inclusion/exclusion) is **PENDING** and required
> before any publication claim of novelty. Statuses below are conservative.

## Search strategy (to be completed)
- Databases: arXiv, Semantic Scholar, OpenReview (PENDING).
- Terms: adaptive computation, mixture-of-depths, conditional computation, dynamic
  routing, mixture-of-experts, continual learning importance, functional reuse.
- Inclusion: mechanisms that allocate/route/reuse compute conditionally. Exclusion:
  pure scaling with no conditional mechanism.

## Nearest mechanisms and CWC's boundary
| Area | Nearest prior art | CWC position |
|---|---|---|
| Adaptive depth | Mixture-of-Depths (Raposo 2024) | CWC does NOT claim to beat MoD (NOT_TESTED); the Jensen-gap result is a *theoretical* identity CWC verifies, orthogonal to MoD's learned router |
| Conditional experts | Switch/MoE (Fedus 2022; Shazeer 2017) | CWC uses load-balance/anti-collapse ideas; makes no MoE-superiority claim |
| Functional reuse | DISeL / HyperFormer (role-conditioned) | CWC-L3 explicitly **NOT_SUPPORTED**: RCFR ties this prior art (not novel in isolation) |
| Continual importance | EWC / SI / MAS | CWC's plasticity governor reuses these; benchmark non-identifiable unbudgeted (NOT_TESTED) |

## Novelty boundary (claim-by-claim)
- **Identifiability theorem + route-decision-cost extension** — the clearest candidate
  novelty: `V_realized = oracle_gap − route_decision_cost`, with the surface-matched
  demonstration that structural difficulty is not cheaply routable. Prior-art overlap:
  **unresolved** pending the systematic search.
- **Jensen-gap = P(m>K) identity** — a derived identity, likely known in the
  adaptive-computation/optimal-stopping literature; CWC's contribution is the exact
  empirical verification, not the identity's discovery. Claimed conservatively.
- All other mechanisms: **not claimed novel** (RCFR ties prior art; routing rides
  surface cues; plasticity non-identifiable).

**No unsupported novelty statement may enter a paper until this review is completed and
each claim's overlap is resolved.**
