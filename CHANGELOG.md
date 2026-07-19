# Changelog

All notable changes to the CWC evidence substrate. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions map to git commits.

## [Unreleased remediation] — 2026-07-19

### Corrected
- Canonical coverage gate now includes plasticity and passes at 96.59% rather
  than failing at 76.32%.
- WP4 process-randomized seed derivation replaced by SHA-256-derived seeds;
  reproduction now writes only to an isolated temporary directory.
- Experiment-level LCG bootstrap replaced after it was shown to produce
  degenerate intervals for `n=8`; two-sided intervals and regression tests added.
- Archived WP4 interpretation narrowed to a same-sample synthetic identity;
  approximate compute parity and historical same-commit preregistration claims
  withdrawn in a superseding epistemic correction.

### Added
- **Unified adaptive-computation value theory** (`docs/ADAPTIVE_COMPUTATION_VALUE_THEORY.md`
  + `experiments/common/adaptive_value_theory.py`): six proved theorems unifying the
  oracle gap, the Pinsker information bound, and the route-decision cost into one
  master inequality `V_net ≤ min{G(λ), Δu·√(I/2)} − c_route`. Strengthens the two
  one-directional gap corollaries to an exact `⇔` (Theorem 2) and adds a bounded
  identifiability window with an explicit cost-saturation threshold `λ★=Δu/δ`
  (Theorem 5). Each theorem is independently re-derived and adversarially
  falsification-tested to ≈10⁻¹⁵ over 10⁴ random decision problems; the exactness
  assertions in the test suite kill any bound-loosening mutation. Mathematical
  scaffolding only — no new `claim_registry.json` entry.
- Read-only semantic evidence validator wired into CI and canonical verification.
- Corrective WP4 v2 evidence bundle with strict <=1% compute parity reporting.
- Exact-total-compute input-blind allocator and explicitly exploratory pilot.
- Fail-closed non-convergence behavior and adversarial cycle test.
- Prospective preregistration integrity policy, debt register, and blocked v3
  exact-compute/noisy-halt/controller-cost protocol draft.

## [1.0.0-d920f79] — 2026-07-16

### Added
- **Routing v3 (local):** end-to-end controller via REINFORCE recovers oracle-level
  routing under a binding budget (`artifacts/wp2-routing-v3-r3c-reinforce/`,
  `SUPPORTED`); surface-matched experiment shows the route decision is the
  computation (`artifacts/wp2-routing-v3-surface-matched/`,
  `ROUTE_DECISION_IS_THE_COMPUTATION`). Theory extended §9:
  `V_realized = oracle_gap − route_decision_cost`.
- Stanford-grade checklist status audit (`docs/CHECKLIST_STATUS.{md,json}`).
- Physical sparse dispatch (`forward_sparse`), surface-leakage audit, corrected
  symmetric NMI / average-rank AUROC, containers, clean-release builder,
  `make reproduce-primary`.
- Documentation-methodology layer (this release): canonical README, methodology,
  hypothesis/claim registries + schemas, V&V traceability, System Card.

### Changed
- Root `README.md` now describes CWC (upstream nanochat README moved to
  `docs/upstream/NANOCHAT_README.md`).
- `CITATION.cff` and `claim_registry.json` refreshed to HEAD `d920f79`.
- Routing v2 claim narrowed (value distillation, label-derived capacity, surface
  cues, no physical saving) after accepting external review.

### Preserved (immutable negatives)
- RCFR ties prior art (`RCFR_NOT_SUPPORTED`); metaplasticity benchmark
  non-identifiable unbudgeted; fractal emergence unsupported (archival).

## [0.x] — 2026-07-15 and earlier
- Consolidation of three sibling projects into one system (`526c6a5`).
- Identifiability theory (`6322bed`); WP4 Jensen gap (`7e53ecd`); WP1
  instrumentation substrate (207 tests, 99.46% cov, 12/12 mutation).
