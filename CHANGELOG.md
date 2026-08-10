# Changelog

All notable changes to the CWC evidence substrate. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions map to git commits.

## [Interventional model-class falsifiability] — 2026-08-10

### Added
- `cwc/counterfactual/falsifiability.py`: profiled composite-null Gaussian intervention model, nuisance envelope, KL/cost design search, equivalence detector, block e-process and fixed-checkpoint global e-value.
- `CSCA-06A-IF`: preregistered finite-budget falsifiability experiment, including latent-vs-aleatoric non-identifiability construction and an explicit nuisance-envelope boundary.
- `CSCA-06A-R1`: new preregistration and fresh cohorts after the parent failed; exactly three cumulative-cost checkpoints with family-wise alpha control.

### Evidence
- Parent `CSCA-06A-IF` remains `NOT_SUPPORTED`: PRIMARY S2 `120/128=0.9375 < 0.95`; independent replication passed but cannot rescue the frozen PRIMARY.
- R1 PRIMARY: S1/S2/S3 `128/128`; N0/N1/N2/N3/E0 `0/128` rejected.
- R1 independent REPLICATION: S1/S2/S3 `128/128`; N0/N1/N2/N3/E0 `0/128` rejected.
- R1 uses the same alpha `0.01`, max cost `256`, nuisance envelope and structural power threshold as the failed parent; only evidence aggregation changed.
- Scalar intervention observations identify total nuisance variance, not a unique latent-confounder versus aleatoric decomposition.
- Added a post-confirmatory information converse: any level-0.01 test targeting power 0.95 needs at least `kl(0.95||0.01)=4.17689895` nats against the closest null. The weak W1 separation rate implies a necessary cost `>=423.71`, exceeding the frozen 256 budget; E0 has zero separation and infinite required cost.

### Scope boundary
`GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED` means only that the declared composite model class is falsifiable on the frozen controlled family. It does not prove graph truth, exclude arbitrary hidden confounding, authorize real-model causal control, or establish a universal information threshold.

## [Structural counterfactual adequacy qualification] — 2026-08-10

### Added
- `CSCA-04-SA`, a seven-phase structural world-model adequacy attack.
- Prospectively calibrated intervention-noise-normalized discrepancy (`IDR`) with frozen balanced candidate×context support.
- `cwc/counterfactual/structural_adequacy.py` and `structural_authority.py`.
- Context-conditional structural authority and fail-closed states for misspecification, insufficient support and zero leverage.
- Independent PRIMARY/replication cohorts plus secondary intervention-allocation, GSS and sample-efficiency diagnostics.

### Evidence
- PRIMARY: 512/512 controlled structurally inadequate cases rejected/falsified; 127/128 known-adequate cases preserved.
- Independent replication: 512/512 inadequate rejected/falsified; 128/128 adequate preserved.
- Zero global authority on zero-cause and context-sign-flip families.
- Collinear observational-identifiability family rejected 64/64 in each cohort despite median factual RMSE about 0.151/0.153.
- GSS is retained as diagnostic-only: under a shared wrong edge it selected spurious `C` as top factual reliance in 16/16 fresh diagnostic seeds while intervention-based adequacy rejected 16/16.

### Scope boundary
`STRUCTURAL_ADEQUACY_SYNTHETIC_QUALIFIED` does **not** authorize shadow inference, real-model replay, semantic real-world causality, biological claims, or active causal control. Next gate: `CSCA-05` composed causal authority on real-model intervention traces.

## [Deferred causal-credit controls] — 2026-08-10

### Added
- `cwc/memory/causal_debt.py`: append-only experimental ledger that separates
  observational eligibility from causal authority, records replay evidence, measures
  cross-context invariance, and gates consolidation fail-closed.
- `cwc/replay/`: deterministic replay scheduling, explicit counterfactual probe
  contracts, and exact paired random-sign max-T statistics.
- `CWC-CDL-01` preregistration and a sealed negative V1 result. The original debt
  rule starved the invariant cause by keeping interventionally dead but observationally
  salient candidates permanently high-priority.
- `CWC-CDL-02` preregistration and a separate resolution-aware V2 result. V2 keeps
  the V1 implementation intact for reproduction, but adds a new priority rule in which
  observational eligibility decays with intervention count and measured causal leverage
  becomes the scheduling term.
- `scripts/causal_debt_gate.py`, included in `verify` and `pr-fast`, binds the V1
  negative parent, V2 synthetic-only scope, checksums, and explicit prohibition on
  biological/VIA escalation.
- Post-confirmatory mechanism ablation and 16-setting stress sweep, both explicitly
  non-authoritative for claim upgrades.

### Evidence
- V1: `CAUSAL_DEBT_CONTROL_NOT_QUALIFIED`.
- V2: `CAUSAL_DEBT_V2_CONTROL_QUALIFIED` **only on the frozen synthetic SCM control**;
  mean paired OOS +0.1665 vs uniform-CF and +0.1932 vs RPE-CF, exact max-T FWER
  p=1.91e-6 / 9.54e-7.
- Ablation attributes most of the exploratory gain to resolution-aware candidate
  scheduling (+0.1654 to +0.1743 under random-context comparisons); balanced context
  coverage contributes only about +0.0077 in the debt condition.
- Stress sweep: V2 mean OOS exceeded each matched control in 15/16 parameter settings;
  the two individual non-superiority settings are preserved, not excluded.

### Scope boundary
No biological mechanism claim, no language-model memory claim, no physical inference
efficiency claim, and no VIA-V2+ authorization.

## [External-audit closure] — 2026-08-08

An independent audit ran four break-in attempts against the gate battery. Two were
repelled, two succeeded — and the two that succeeded were in the same place: the gates
verified *code* but never verified that a registered status matched the evidence it
claimed to rest on.

### Broken by the audit (reproduced, then closed)
- **Registry statuses were unguarded.** `CWC-L3-rcfr` and `CWC-L2c-e2e-straightthrough`
  (`NOT_SUPPORTED`) and `CWC-L7-pareto` (`NOT_TESTED`) were flipped to `SUPPORTED` by
  hand and `make -f Makefile.cwc pr-fast` still printed ALL GATES PASSED. Promoting
  `CWC-L7-pareto` asserts a compute-equivalent Pareto win over MoD/MoE that has never
  been run; nothing in the battery objected.
- **Bundle numbers were unguarded in the every-run gate.** Rewriting
  `artifacts/wp2-routing-v3-r3c-reinforce/verdict.json` (`worst_seed_auroc` 1.0 → 0.02,
  `mean_balanced_acc` 0.994 → 0.01) while leaving the verdict string intact passed
  `validate-evidence` and `doc-gate`. Only `verify-evidence` caught it — and that target
  runs in `verify-full`, not in `verify` or `pr-fast`.
- **The coherence ladder was decoupled from the ledger.** `coherence_audit._LADDER` is
  six hand-written rows whose ids ("wp3-rcfr (ties DISeL-with-role)") do not appear in
  `claim_registry.json`. Theorem C's "every registered verdict is coherent" was
  reproducing its own copy, not the 43-claim registry.

### Added
- **`scripts/verdict_binding_gate.py` + `verdict-binding` target**, in both `verify` and
  `pr-fast`. Every claim now carries `verdict_binding` (file, pointer, expected) and the
  gate checks: binding present (fail-closed); file tracked in the registry's own stamped
  commit; the value at the pointer equals `expected`; `expected` has a declared polarity
  in a table that lives *in the gate's source*, not in the registry; that polarity equals
  the one implied by `status`; the file's SHA-256 matches its `SHA256SUMS` entry — which
  pulls the checksum guarantee out of `verify-full` into every run; `SUPPORTED_NARROWED`
  names a non-empty `limitations`; and every ladder row resolves to a real `claim_id`
  with the registry status it declares.
- The gate runs its own falsifier first (`--self-test`): four injected defects must be
  detected and the unmutated registry must pass, or the gate fails before it is trusted.
- `tests/test_verdict_binding_gate.py` (9 tests) replays each successful break-in.
- Stated limit, not glossed: a *coordinated* rewrite of verdict file + SHA256SUMS +
  registry is a git-history and review problem, and this gate does not claim to catch it.

### Changed
- `schemas/claim.schema.json` accepts `verdict_binding`; all 43 claims bound (41 to
  sealed verdicts, 2 `NOT_TESTED` unbound by design).
- `experiments/common/coherence_audit._LADDER` rows now carry `registry_claim_id` and
  `registry_status`.
- **Novelty narrowed.** The audit also found that `CWC-RIGOR3-pinsker` — the last
  unqualified `NOVELTY_CANDIDATE` — was argued against Pinsker and rational inattention
  but never against the economics-of-information literature on the marginal value of the
  first unit of information, which was absent from `references.bib` entirely. Added
  Radner & Stiglitz (1984), Chade & Schlee (2002), De Lara & Gilotte (2007), Whitmeyer
  (2024), De Lara & Gossner (2020) (70 machine-resolved references, was 65). The
  dichotomy *as a phenomenon* is now `OVERLAP_CONCEDED`; only its quantitative form —
  exponents in nats, tied to Pinsker tightness, with `c = std(D)/Δu` — remains a
  candidate, recorded as `NOVELTY_CANDIDATE (NARROWED)`. See
  `RELATED_WORK_AND_NOVELTY_REVIEW.md` §2.5.1.

## [Audit-closure] — 2026-07-20

Closure of a full 4-axis adversarial audit (claim↔evidence, theory soundness,
instrumentation code, methodology/gates). The verify gate was independently
reproduced GREEN before and after. No claim was falsified; the audit found a
coherent class of "advertised rigor > enforced rigor" gaps plus one latent
fail-open, all closed here.

### Fixed
- **Energy fail-open (F1, real defect).** `NVMLPowerSampler.stop()` returned a
  fabricated `joules=0.0` with `available=True` on a <2-sample (unmeasurable)
  window, violating the module's own contract. Now returns `available=False`,
  `confidence="unavailable"`; the test that blessed the defect now asserts it.
- **Energy exclusion is now code-enforced (F2).** `enable_energy` requires an
  explicit `energy_instrument_invalid_ack=True` — the INSTRUMENT_INVALID
  discipline is a fail-closed gate, not operator convention.
- **Registry provenance staleness (M2/M3).** `claim_registry.git_commit` was 51
  commits stale and pointed at a tree missing three of its own required
  artifacts; the doc gate's docstring claimed `==HEAD` but only checked ancestry.
  Registry re-stamped; `doc_status_gate.py` now fails closed unless every
  required_artifact already exists in the stamped commit's tree; docstring
  corrected.
- **Frozen-negative evidence gate (M4).** RTM REQ-010 declared `verify-evidence`
  covers `artifacts/history/`, but neither gate touched it. Both `Makefile.cwc
  verify-evidence` and `validate_evidence.py` now check the three frozen-negative
  bundles (checksum + SHA256SUMS/CLAIM_BOUNDARY.json).

### Corrected (honesty)
- WP4 primary bundle carries a `SUPERSEDED.md` banner (checksum-safe) pointing to
  the epistemic correction; its `compute_matched: true` / `..._CONFIRMED` verdict
  is retracted at interpretation while the sealed files stay verbatim.
- Statistical Analysis Plan: "hierarchical (seed→corpus→example) bootstrap"
  corrected to the implemented flat seed-unit bootstrap.
- Theory labeling: coherence "Theorem C" relabeled an internal-consistency audit
  (not a coherence proof); the inference-certificate coverage, the Pinsker
  small-rate dichotomy, and the master-inequality λ-unification carry honest
  scope caveats. Theorems 1–5, 4′, RI-optimality and Efficiency-E are unchanged
  (genuinely proved).
- `act_j_pilot` labeled EXPLORATORY / not-preregistered / not a claim-ladder
  entry, now with `verdict.json` + `SHA256SUMS`; SYSTEM.md preregistration prose
  reconciled with the RETROSPECTIVE_PROTOCOL disclosure. `CWC-L0` metric corrected
  to the artifact's actual test count.

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
- **Act-J pilot — a trained neural controller realises V*(R)** (`experiments/act_j_pilot/`
  + `artifacts/act-j-pilot/`): the empirical bridge from the information-market theory to a
  learning system. A real MLP controller `context→P(a|c)` trained by Adam on the
  rational-inattention objective `E[U]−β·I(C;A)` (GPU, torch 2.9) converges to the analytic
  rate function `V*(I)` to machine precision across 2 regimes × 3 seeds × 4 information
  prices (worst gap 0.0000, verdict `TRAINED_CONTROLLER_REALISES_V_STAR`), and exhibits the
  phase transition — at a high info price the critical problem routes (V=0.083) while the
  regular one abstains (V≈0). Scales to |C|=8,|A|=5 (worst gap 8.4e-7). A second, noisy-sensor
  controller sees only a confused observation O and learns the Bayes value V(O), bounded by
  V(O)<=V*(I(C;O)); the symmetric confusion sensor is rate-optimal IFF the problem is
  context-exchangeable (full permutation symmetry, any |C| — verified |C|=3 too), NOT merely
  critical: a critical-but-non-exchangeable problem still wastes value (inefficiency
  0.05-0.10). [Corrected in the destruction stage from an over-generalised 2x2 phrasing.]
  The inefficiency is the measurable cost of a channel not shaped to the decision. Fast pytest.
  Compute-matched (the Act-J shape on the FLOP axis): mechanisms carry FLOP costs
  (cheap=1, expensive=4); a trained adaptive router is compared to the best context-blind
  policy at EQUAL average compute. Under a binding budget the adaptive router strictly
  dominates static by 0.25 at matched FLOPs -- exactly the constrained oracle gap the theory
  predicts (same 0.25 as budgeted routing-v2) -- and ties when a mechanism weakly dominates.
  The compute-equivalent advantage question answered at tiny synthetic scale, matching theory;
  a proof of concept for L7, NOT the cloud-scale Pareto (still cloud-blocked). Fast pytest (8).
  Real-transformer version (`transformer_depth.py`): adaptive depth on a pointer-following
  task (easy=1-hop@depth-3, hard=3-hop@depth-4). HONEST finding (destruction stage): adaptive
  is never worse than static at matched compute (once both depths converge — the deeper model
  trains slower), but the strict gain is NOT robust — on some seeds the shallow model learns
  the hard task and the separation collapses (shallow-on-hard 0.96/0.41/0.21 -> gain
  0.01/0.15/0.20, mean +0.12, min +0.01). Two earlier task designs were retracted as not
  depth-separated once trained. Mirrors the programme's WP2 bimodal-collapse: adaptivity pays
  iff genuinely separated, which is a seed-dependent empirical accident, not a promise.
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
## 2026-08-10 — ACT-R&D-01 evidence ingestion / P0 pass

- added primary-source research registry, claim ledger, contradiction matrix, executable hypotheses, reproduction queue and fail-closed ingestion gate;
- reproduced a narrow S01 Skill/Luck Counterfactual-Shapley property and qualified an exact synthetic OOD causal-credit target over 7,962,624 counterfactual structural evaluations;
- preserved a preregistered S03 controlled latent-dynamics negative result: h=8 OOD robustness reached 54/64 seeds versus the frozen >=56/64 gate;
- no external mechanism received architecture-promotion authority.

## 2026-08-10 — ACT-R&D-02 execution / CSCA-01

- added immutable evidence ingestion, claim-attack flags, evidence graph, human governance records, run telemetry, and a C0→C3 fail-closed compute governor;
- executed CSCA-01 on 49,152 controlled trajectories with 24,625,152 counted structural counterfactual evaluations; exact counterfactual credit reproduced across frozen primary/replication cohorts and zero-cause nulls;
- retained a source-provenance quarantine because full primary paper bytes/code were not materialized, so paper-reproduction and architecture-promotion authority remain false;
- preserved CSCA-01A as an exploratory no-H4 diagnostic showing that counterfactual-model structural error propagates directly into false causal credit;
- broad environment-available suite: 299 PASS / 23 SKIP; full collection remains blocked by rustbpe/tomli/hypothesis/pyarrow.

## 2026-08-10 — CSCA-05 direct-intervention shadow qualification

- Fixed an `Engine` vocabulary-contract bug exposed by actual runtime execution.
- Added deterministic ablation-Shapley and antithetic finite-budget estimators for explicit byte-span interventions.
- Trained independent small nanochat GPT checkpoints for calibration, PRIMARY, and REPLICATION cohorts.
- Qualified a narrow shadow-only path: zero accepted-case false authority, exact-teacher top agreement 1.0, and zero generation/state interference in both confirmatory cohorts.
- Preserved boundaries: mostly recency-dominated task, intervention-operator sensitivity, ~4x CPU p50 sidecar overhead, no GPU/replay/active-control promotion.
- Repaired the CSCA-05 H4 record to the canonical `HumanDecision` schema without changing frozen scientific design fields; repair is explicitly documented post-execution.
