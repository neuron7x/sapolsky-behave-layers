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
  Adaptive extension: a tie-safeguarded parametric-bootstrap debiasing recovers the
  power the worst-case bound discards (0.77→0.92, +15 points) at fixed validity —
  false-positive rate ≤ δ on every null incl. least-favorable ties — by estimating the
  actual separation-dependent bias and falling back to the conservative bound near the
  non-differentiable tie (where the bootstrap is inconsistent, Bickel-Freedman); near
  the boundary it correctly defers rather than green-lighting.
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
  Universality: a general-context binary-signal solver confirms the transition is NOT a
  binary artifact — at |C|=3 the regular problem gives exponent 1.12 (Pinsker ratio 0.11,
  loose), the critical problem exponent 0.54 (ratio 0.67, tight), matching the binary case.
  Exact critical constant (Theorem 4'): at a symmetric binary indifference point the
  Pinsker ceiling is ATTAINED, not merely order-tight — V*(R)=Δu√(R/2)(1−R/6+O(R²)),
  c=1, verified to machine precision by a closed-form solver (1−ratio = R/6 to every
  digit). Non-symmetric critical points keep Θ(√R) with c≤1, exact only on the
  symmetric locus — the sharpest statement of when routability is attained.
  Sharp general solver: max_channel[V-beta*I] is the rational-inattention problem
  (Matejka-McKay 2015); its Blahut-Arimoto fixed point + beta-bisection gives the exact
  V*(R) for any finite |C|,|A| (optimal_value_at_rate_ri). Cross-validated three ways —
  reproduces the closed-form critical value to 1.7e-16, matches the exact binary grid,
  and strictly beats the binary-signal lower bound at |C|=|A|=3 (0.081>0.075), finding
  the optimal stochastic channel. Sharpened exponents: 0.97 regular, 0.498 critical.
  Marginal value of information: the shadow price beta(R)=dV*/dR [utility/nat]
  (marginal_value_of_information), verified to equal the numerical derivative of V*;
  decreasing in R -> V* is concave (settles Prop 1); finite as R->0 (regular) vs
  divergent (critical). Fractal energy link: decision value per joule <= beta/(k_B T)
  (utility_per_joule_ceiling) couples the rate function to the neuron budget's J/bit
  floor — the same information-market price from the abstract decision to the ion channel.
  Economic optimum (Theorem 4''): with per-nat cost kappa the net-optimal information
  budget R* solves beta(R*)=kappa (marginal value = marginal cost), and routing pays iff
  beta(0+)>kappa — regular problems route iff kappa<sigma (the sensitivity threshold),
  critical problems always route (first nat infinitely valuable). optimal_information_budget;
  verified beta(R*)=kappa, net maximised, thresholds correct. Turns "how tight is Pinsker?"
  into "how many bits to buy, and whether to buy any" — the operational Act J decision.
  CWC application: applying the apparatus to the real routing-v2 experiment shows the
  binding budget places it near the indifference manifold (margin 0.002) yet strongly
  identifiable (G=0.248) — the most information-efficient regime, where the marginal
  value of a difficulty-signal is amplified ~17x (beta(1e-4)=17.6 vs ~1.05 regular).
  The theory now explains the empirical CE gap, not merely bounds it.
  General critical constant (Theorem 4'''): at any two-action critical point with
  D=U[.,a]-U[.,b], V*(R)=sqrt(R*Var(D)/2), so kappa=std(D)/sqrt2 and the Pinsker-ratio
  limit is c=std(D)/Du <= 1, equality iff |D|=Du a.s. (recovers c=1 symmetric).
  critical_leading_constant; the formula predicts the RI solver to 2e-3 (c=1.00,0.47,0.43).
  The routability attainment factor on the whole indifference manifold, closed exactly.
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
