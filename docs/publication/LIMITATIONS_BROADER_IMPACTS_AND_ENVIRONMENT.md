# Limitations, Broader Impacts and Environment

## Limitations
- **Synthetic-only.** Every confirmatory result is on procedurally-generated,
  mechanism-separable benchmarks. No real-workload evidence exists yet.
- **Small scale.** Depth ≤ 12 on a 4 GiB GPU; no scale generalization tested.
- **No compute-equivalent Pareto** vs MoD/MoE (the decisive architectural test) —
  NOT_TESTED, cloud-blocked.
- **No independent replication.** A re-run by the author is not replication.
- **Surface caveat.** The strongest routing positive (CWC-L2a) still has surface cues;
  the surface-matched study shows structural routing is not cheaply learnable.
- **Energy uninstrumented.** INSTRUMENT_INVALID on this hardware; excluded from all claims.

## Broader impacts
CWC is basic research into whether adaptive computation can be causally justified. The
route-decision-cost result is a *cautionary* contribution: it bounds when adaptive
routing can save compute, discouraging over-claimed efficiency. No dual-use or
deployment concern at the current scope (LOCAL_RESEARCH_ONLY).

## Environment / compute footprint
All results reproduce in seconds–minutes on CPU / RTX 3050; total training cost $0. The
cloud tiers that would be needed for a scale claim are estimated in
`docs/reproducibility/EXPECTED_RUNTIME_HARDWARE_AND_COST.md` ($1.5k–$50k depending on
scope), and are explicitly gated behind a cheap route-decision-cost pilot first.
