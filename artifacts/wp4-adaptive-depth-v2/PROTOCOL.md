# WP4 v2 Correction Protocol

This is a post-audit corrective rerun, **not a confirmatory preregistration**.
It was initiated after discovery of three defects in the archived WP4 bundle:
process-randomized seed derivation, a degenerate experiment-level bootstrap for
`n=8`, and an overly permissive compute-parity gate.

Fixed before this rerun:

- SHA-256 seed derivation from `(experiment, seed, distribution)`;
- bootstrap resampling with `random.Random` and a non-degeneracy regression test;
- two-sided CI serialization;
- compute parity as relative mismatch <= 1%;
- identity verdict separated from the compute-parity gate.

This bundle may verify only a synthetic same-sample identity. It cannot support
a Pareto, novelty, learned-controller, or independent-prediction claim.
