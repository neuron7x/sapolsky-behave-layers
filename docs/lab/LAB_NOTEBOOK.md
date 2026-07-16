# CWC Laboratory Notebook

Running log of decisions, anomalies, errors, and interpretations. Per-run provenance is
in `EXPERIMENT_LEDGER.jsonl`; this file records the *reasoning*.

## 2026-07-16
- Routing v2 result narrowed after external review identified three leaks (privileged
  target, label-derived capacity, surface cues). Verified all three in-code; narrowed
  without deleting the artifact.
- **Key decision:** tested whether the R3-C collapse was optimization or signal. Ran
  REINFORCE (H_opt) vs straight-through (H_deep). Anomaly: at λ≤0.5 the controller routed
  everything to the semantic path and the route *inverted* (AUROC→0) — resolved as the
  identifiability theory's prediction (quality-dominant without a binding budget).
- **Interpretation:** collapse was an estimator artifact; value localizes to cheap
  route-signal computability. Surface-matched study confirms structural routing is not
  cheaply learnable → route-decision-cost extension to the theory.
- Error caught: a Cyrillic path typo (`Desктоп`) misplaced one doc; moved and cleaned.

## Earlier
- Consolidation of three sibling projects into one system; WP1 instrumentation closure;
  identifiability theory derived; WP4 Jensen gap confirmed to machine precision.
