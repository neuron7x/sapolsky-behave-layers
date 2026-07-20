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
- **Inference breakthrough: a calibrated pilot identifiability certificate**
  (`docs/IDENTIFIABILITY_INFERENCE.md` + `experiments/common/identifiability_inference.py`):
  the step from converse-only upper bounds to a decidable, error-controlled action.
  Because the oracle gap `G` is a `max`-functional, the plug-in estimate is upward
  biased (Jensen) and the naive `Ĝ>0` rule has an uncontrolled false-positive rate
  (0.55 at n=50, up to 1.0 on a tied null). The debiased one-sided bound
  `G_lo = Ĝ − sd√(2ln|A|) − (sd/√|C|)√(2ln(2/δ))` satisfies `P(G≥G_lo)≥1−δ`, so
  `G_lo>0` certifies identifiability and `G_lo>c_route` certifies positive value, each
  with false-positive rate ≤ δ; sample complexity `n*=⌈(σK/G)²⌉`. Monte-Carlo
  calibration confirms FPR ≤ δ and power → 1; the max-bias term is shown load-bearing
  (dropping it breaks calibration in the many-action regime — mutation-tested). This
  is the machine that decides the Act J cloud spend with a validity proof attached.
- **Value-of-information rate function and the Pinsker phase transition**
  (`docs/VALUE_OF_INFORMATION_RATE_FUNCTION.md` + `experiments/common/value_of_information_rate.py`):
  computes the sharp `V*(R) = max{V(Z) : I(C;Z) ≤ R}` that the routability ceiling only
  bounds, and settles the open "the bound can be loose" remark. New theorem (small-rate
  dichotomy, computed + proved): at a REGULAR problem `V*(R)=Θ(R)` so Pinsker is
  asymptotically infinitely loose (ratio→0, exponent 0.98); at a CRITICAL problem (two
  actions tie — the measure-zero indifference manifold) `V*(R)=Θ(√R)` so Pinsker is
  asymptotically exact (ratio→1, exponent 0.55). Locates precisely when a century-old
  inequality is tight for decisions; tells CWC that routability certificates are
  conservative off the indifference manifold. Exact binary-context solver + adversarial
  harness (envelope, monotonicity, saturation, dichotomy); mutation-tested. No claim entry.
- **Machine-checked coherence + efficiency proof** (`docs/MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md`
  + `experiments/common/coherence_audit.py`): Theorem C proves the whole claim ladder
  is internally consistent — every recorded verdict equals the sign of its master
  certificate `Γ = min{G(λ), Δu√(I/2)} − c_route`, reproduced from the programme's own
  utility matrices (routing budgeted G=0.248, three dominance-negatives at G=0, one
  computation veto); 0 contradictions, and the three vetoes partition all negatives.
  Theorem E proves the identifiability predictor is `Θ(|C||A|)` and optimal (adversary
  argument: every entry must be read), measured `reads == |C||A|`. The auditor is
  falsifiable — `falsify_coherence` injects a weakly-dominant claim tagged SUPPORTED
  and confirms it is flagged. Meta-theoretical; no `claim_registry.json` change.
- **Verified neural information-budget model** (`docs/NEURON_INFORMATION_BUDGET.md`
  + `experiments/common/neuron_information_budget.py`): estimates single-neuron
  throughput (≈10 bits/s cortical, ~150 sensory), energy per bit (≈2×10⁻¹¹ J/bit ≈
  2×10⁸ ATP/bit ≈ 10⁹–10¹⁰ Landauer floors), and a non-linear network extrapolation
  (information saturates at `I_1/ρ`, energy super-linear `N^α`, bits/joule declines).
  Uncertainty is Monte-Carlo-propagated over literature anchors (Attwell & Laughlin
  2001; Laughlin et al. 1998; Strong et al. 1998); per-neuron power is cross-checked
  by three independent routes agreeing within ~15% at the medians. A falsification
  harness enforces the Landauer floor, positivity, and the saturation/super-linear/
  efficiency-decline laws over 10⁴ draws; exactness assertions kill bound-dropping
  mutations. Physical grounding of the value theory's route-decision cost — no new
  `claim_registry.json` entry.
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
