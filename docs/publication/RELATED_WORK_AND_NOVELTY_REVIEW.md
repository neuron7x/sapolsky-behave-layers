# Related Work and Novelty Review

> **Search-completeness disclosure.** This is a *working* review of the nearest prior art
> actually relevant to the current claims, not a completed systematic survey. A full
> systematic search (databases, dates, inclusion/exclusion) is **PENDING** and required
> before any publication claim of novelty. Statuses below are conservative.

## Search strategy (partial, 2026-07-20)
- Databases searched in this pass: arXiv and OpenReview. Semantic Scholar and formal
  backward/forward citation chasing remain PENDING.
- Terms: adaptive computation, mixture-of-depths, conditional computation, dynamic
  routing, mixture-of-experts, continual learning importance, functional reuse.
- Inclusion: mechanisms that allocate/route/reuse compute conditionally. Exclusion:
  pure scaling with no conditional mechanism.

## Nearest mechanisms and CWC's boundary
| Area | Nearest prior art | CWC position |
|---|---|---|
| Adaptive depth | Mixture-of-Depths (Raposo 2024) | CWC does NOT claim to beat MoD (NOT_TESTED); the Jensen-gap result is a *theoretical* identity CWC verifies, orthogonal to MoD's learned router |
| Learned halting | ACT (Graves 2016), PonderNet (Banino et al. 2021), Universal Transformer (Dehghani et al. 2018) | Adaptive stopping is established prior art; CWC claims no novelty for it |
| Conditional experts | Switch/MoE (Fedus 2022; Shazeer 2017) | CWC uses load-balance/anti-collapse ideas; makes no MoE-superiority claim |
| Functional reuse | DISeL / HyperFormer (role-conditioned) | CWC-L3 explicitly **NOT_SUPPORTED**: RCFR ties this prior art (not novel in isolation) |
| Continual importance | EWC / SI / MAS | CWC's plasticity governor reuses these; benchmark non-identifiable unbudgeted (NOT_TESTED) |

## Novelty boundary (claim-by-claim)
- **Identifiability theorem + route-decision-cost extension** — the clearest candidate
  novelty: `V_realized = oracle_gap − route_decision_cost`, with the surface-matched
  demonstration that structural difficulty is not cheaply routable. Prior-art overlap:
  **unresolved** pending the systematic search.
- **Paid halt-information audit** — v4 tests whether the synthetic allocation result
  survives when the successor read that reveals convergence is inside the shared
  budget. This is an evaluation/identifiability contribution candidate, not a new
  adaptive-depth mechanism; novelty remains unresolved pending citation chasing.
- **Jensen-gap = P(m>K) identity** — a derived identity, likely known in the
  adaptive-computation/optimal-stopping literature; CWC's contribution is the exact
  empirical verification, not the identity's discovery. Claimed conservatively.
- All other mechanisms: **not claimed novel** (RCFR ties prior art; routing rides
  surface cues; plasticity non-identifiable).

**No unsupported novelty statement may enter a paper until this review is completed and
each claim's overlap is resolved.**

## Primary sources checked in the partial pass

- Graves, *Adaptive Computation Time for Recurrent Neural Networks* (2016),
  <https://arxiv.org/abs/1603.08983>.
- Dehghani et al., *Universal Transformers* (2018),
  <https://arxiv.org/abs/1807.03819>.
- Banino et al., *PonderNet: Learning to Ponder* (2021),
  <https://openreview.net/forum?id=1EuxRTe0WN>.
- Raposo et al., *Mixture-of-Depths* (2024),
  <https://arxiv.org/abs/2404.02258>.
