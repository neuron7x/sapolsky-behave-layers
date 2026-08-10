# COGNITIVE WIRING CORE — Unified System

Single canonical repository for the CWC research programme: an evidence-first
investigation of whether a causally-controlled adaptive-computation architecture
beats static Transformers / MoE / dynamic-compute systems at equal budget. This
document is the entry point and the map. Consolidated 2026-07-16 (the two former
sibling projects were merged in; see `legacy/` and `experiments/fractal_multiscale/`).

## What this system IS (honest one-line)
A verified measurement substrate + a falsification harness that has produced
**two claim-tier positives** (adaptive routing is causally real; adaptive
compute allocation achieves the theory-predicted Jensen gap) and **four
claim-tier negatives**, plus a **mathematical theory** that unifies and predicts
them all. It is not yet an architecture with a proven Pareto advantage at scale.

**WP4 corrected interpretation** (`docs/vnv/EPISTEMIC_CORRECTION_WP4_2026-07-19.md`):
the substrate verifies the algebraic identity adaptive−static =
`P_sample(m>K)` under an exact halt oracle. It is a useful positive control, not
an independently predicted empirical effect or an exactly compute-matched Pareto
result; adaptive uses `E_sample[m]` hops while static uses `round(E_sample[m])`.

## Causal-credit / counterfactual-model sub-line — current boundary

- `CSCA-01`: exact counterfactual Shapley separates the controlled true cause from confounders/non-causes (`SUPPORTED_NARROWED`).
- `CSCA-02-UA`: global uncertainty/abstention policy failed coverage/context qualification (`NOT_SUPPORTED`); shadow inference remained blocked.
- `CSCA-03R`: CRN/antithetic finite-budget credit estimation qualified on controlled SCMs; variance-only authority was falsified.
- `CSCA-04-SA`: prospective interventional structural-adequacy gate qualified **synthetically** across fresh PRIMARY and independent replication cohorts. It detects controlled world-model misspecification that factual fit/GSS can miss and scopes context-varying mechanisms as `CONTEXT_CONDITIONAL_ONLY`.
- `CSCA-05-RUNTIME`: a **narrow direct-intervention shadow measurement path** is qualified on independently trained small nanochat GPTs. Under the frozen `do(4-byte span=ASCII_SPACE)` operator, a two-pair antithetic ablation-Shapley estimator matched the exact teacher on every accepted PRIMARY/REPLICATION trace with zero base-output or model-state mutation. This is not broad shadow-inference authority: the task is mostly recency-dominated, intervention-operator invariance is incomplete, CPU sidecar overhead is about 4x p50, and no GPU/replay/active-control claim is authorized.
- `CSCA-06A-IF`: the first finite-cost composite-null falsifier is a **frozen negative**. Null/equivalence safety held, but PRIMARY S2 reached only 120/128=0.9375 against a preregistered >=0.95 power gate; replication cannot rescue PRIMARY.
- `CSCA-06A-R1`: a new, preregistered fixed-checkpoint global shared-nuisance evidence aggregator qualified **narrowly** at the same alpha=0.01 and max intervention cost=256: S1/S2/S3 were 128/128 in fresh PRIMARY and again 128/128 in independent REPLICATION, while N0-N3/E0 were 0/128 rejected per family. This falsifies only the declared graph-component+nuisance model class; it does not establish graph truth or separate hidden-confounder variance from aleatoric variance.
- `CSCA-06B-OP`: exact credit is robust across two declared same-context stochastic donor-resampling soft-intervention kernels: top/sign agreement and robust coverage are 1.0 in pooled/PROSE/CODE for both PRIMARY and REPLICATION. However every robust case is `A_RECENT`; no semantic/content mechanism follows.
- `CSCA-06C-R1`: content-position rotation attacks that recency confound. Every fully resolved case tracks fixed position (`PositionTracking=1.0`) rather than moved content (`ContentTracking=0.25`), but replication resolution coverage is only 0.333 PROSE / 0.458 pooled, below the frozen 0.50 gate. Final verdict: `POSITION_CONTENT_MECHANISM_UNRESOLVED`; content-specific causal credit is NOT_SUPPORTED and position/locality is not promoted either.

- `CSCA-07-PR`: passive-replay identifiability boundary qualified. An anytime-valid factual-trace e-process falsifies wrong observable transition laws, but exact counterexamples prove that observationally equivalent latent topologies can share both the observable path and Jacobian spectrum; a stable invariant hidden replay attractor can carry zero factual information; and zero within-model fiber entropy does not identify latent semantics. Therefore passive non-rejection never promotes causal authority without explicit additional identifying assumptions.

**ACT-R&D-03 remains negative for broad learned-model causal authority.** CSCA-06A-R1 closes a controlled model-class falsifiability subproblem; CSCA-06B qualifies only operator-family robustness; CSCA-06C blocks a content-specific interpretation. Student amortization, replay and active causal control remain blocked.

## Claim ladder — current state
| Level | Claim | Status | Evidence |
|---|---|---|---|
| L0 measurement substrate | instrumentation deterministic & validated | **SUPPORTED** | `artifacts/wp1-release/`, 207 tests, 99.46% cov, 12/12 mutation |
| L1 benchmark identifiability | a benchmark with a real adaptive-compute advantage exists | **SUPPORTED** | `artifacts/wp2-routing-v2/` oracle gap 99.8% |
| L2 routing causality | learned controller routes causally, beats all controls | **SUPPORTED (NARROWED)** — under counterfactual value distillation, label-derived test capacity, surface cues present, no physical compute saving; see `artifacts/wp2-routing-v2/claim_boundary.json` | `artifacts/wp2-routing-v2/` bal 1.0, NMI 1.0, AUROC 1.0, 8 seeds |
| L2a end-to-end routing (leaky benchmark) | leakage-free-*target* controller routes without value distillation | **SUPPORTED under a binding budget** — the earlier straight-through *collapse* was an estimator artifact; a REINFORCE controller (L=L_task+λ·C_use) reaches AUROC 1.0 with NO privileged target / NO label-derived capacity — but only at λ≥1 (binding budget), and surface cues are still present | `artifacts/wp2-routing-v3-r3c-reinforce/` learned 0.009 vs random 0.48, 8 seeds |
| L2b route-decision cost (surface-matched) | can a cheap controller route when difficulty is purely structural? | **NO — ROUTE_DECISION_IS_THE_COMPUTATION** | `artifacts/wp2-routing-v3-surface-matched/` — on a surface-matched task neither a cheap nor an attention controller routes above chance (AUROC ~0.51, no loss saving) even under *direct supervision*; predicting the route costs ~the expensive computation |
| L2′ synthetic allocation identity | halt-oracle adaptive−static equals empirical tail mass P_sample(m>K) | **SUPPORTED_NARROWED** | archived WP4 bundle + epistemic correction; no exact compute-parity claim |
| L2′′ frozen operator-hop allocation | halt-conditioned allocation beats input-blind allocation at identical frozen operator hops | **SUPPORTED_NARROWED_INTERNAL** | `wp4-exact-compute-v31`; free halt oracle, not end-to-end compute parity |
| L3 functional reuse (RCFR) | one module = many functions, novel | **NOT_SUPPORTED** | `artifacts/wp3-rcfr/` — real but ties DISeL (prior art) |
| L4 controlled plasticity | budgeted metaplasticity gap is real AND a learned governor recovers it | **SUPPORTED_NARROWED** — oracle gap confirmed OUT-OF-SAMPLE (16 held-out seeds, λ frozen a priori: G_lo 0.111>0, 16/16 seeds); AND a reward-only REINFORCE governor recovers 100% of it on held-out (8/8 controller seeds, NULL falsifier at 0). Synthetic, given-context, wide-margin; NO L7 | `artifacts/wp3-plasticity-v2-confirmatory/` (confirmatory) + `artifacts/wp3-plasticity-v3-governor/` (learned governor); `artifacts/wp3-plasticity-v1/` null + `artifacts/act-j-pilot-decision/` pilot |
| L4b inferred-context boundary | governor value is bounded by I(C;Z) (route-decision cost) | **SUPPORTED** — under a noisy context observation, held-out recovery tracks the grounded prediction 1−2.146p to ±0.001, is monotone in I(C;Z), and the governor abstains 8/8 at zero info (boundary p*≈0.466). Plasticity analog of L2b; instantiates V_realized ≤ oracle_gap − c_route | `artifacts/wp3-plasticity-v4-inferred/` |
| L4c credit-collapse scaling | governor collapse margin follows the (σ/Δ)² law | **NOT_SUPPORTED** — FROZEN FALSIFICATION: a collapse is real (recovery 1.0→~0.3 as Δ→0.02) but Δ* does NOT scale with noise (ratio 0.91 vs predicted ~2.0); REINFORCE's σ-dependent step cancels it. My own prediction, refuted | `artifacts/wp3-plasticity-v5-thinmargin/` |
| L4d collapse scaling (higher-power) | collapse margin follows (σ/Δ)² law in budget & noise | **NOT_SUPPORTED** — Δ\* scales with budget (monotone, 0.0567→0.0140) but STEEPER than 1/√N (ratio 0.247, ~N^−0.68); noise anti-scales (0.5<1, more noise helps). The sample-complexity law governs neither axis. Frozen (L4c survives higher power) | `artifacts/wp3-plasticity-v6-scaling/` |
| L4e collapse mechanism | the collapse is a pure 2-arm logit phenomenon | **NOT_SUPPORTED** — 2-arm ablation is drift-limited (Δ\*∝N^−1.12, confirming dg/dt∝Δ·π(1−π)) but the full governor is N^−0.65; dead-arm suppression adds diffusion. Noise-as-exploration IS reproduced (2-arm). Partial explanation, hypothesis falsified | `artifacts/wp3-plasticity-v7-mechanism/` |
| L4f collapse-exponent arm scaling | exponent shallows monotonically with arm count | **SUPPORTED** — K={2,3,4,6,8} → exponent −1.03/−0.64/−0.46/−0.45/−0.09, monotone shallowing from the 2-arm drift limit past diffusion (dead arms inject diffusion; exp(8)−exp(2)=0.93). Closes L4e. Caveats: overshoots −0.5→0, exponents grid-sensitive | `artifacts/wp3-plasticity-v8-armscaling/` |
| L4g cost-model robustness | L4 gap survives any monotone cost shape | **SUPPORTED** — G_lo>0 for linear/sqrt/log/square (0.111/0.101/0.035/0.043), governor recovery 1.0 each; monotone transforms preserve the cost ordering. Magnitude cost-shape dependent (log→0.035). Strengthens L4 | `artifacts/wp3-plasticity-v9-costrobust/` |
| L4h context-scaling | identifiability+governor generalize to more contexts | **SUPPORTED** — \|C\|=2/3/4/6 at constant per-context budget: G_lo 0.084→0.685 (grows), governor recovery ≥0.952; contexts don't interfere. Generalizes the 2-context result | `artifacts/wp3-plasticity-v10-contexts/` |
| L4i rate-function bridge | learned governor realises master V*(R) | **SUPPORTED** — V_gov ≤ V*(I) everywhere (ceiling holds), saturation ≥0.924 (≥0.98 high-info); plasticity analog of act-j's TRAINED_CONTROLLER_REALISES_V_STAR. Ties the sub-line to the information-market theory | `artifacts/wp3-plasticity-v11-ratebridge/` |
| L4j sub-line consistency | registry status matches every artifact verdict | **SUPPORTED** — governance cross-check: 9 L4 claims, 0 polarity mismatches, 0 orphan bundles (auditor self-exempt). Closes the status⟷verdict gap the other gates miss | `artifacts/wp3-plasticity-v12-consistency/` |
| L4k falsification boundary | line survives its decisive foundation nulls | **SUPPORTED** — gap present only with a real interaction (0.111); vanishes under additive/collapsed/aligned-best nulls (recovery 0). Harness caught my own broken null → disclosed fix. Foundation sound | `artifacts/wp3-plasticity-v13-killtest/` |
| AC1 adaptive-compute identifiability (2nd mechanism) | oracle compute-allocation beats fixed compute | **SUPPORTED** — real trained recurrent model (1 iter = shift-by-1), oracle K=d beats fixed K: G_lo 0.621/0.455/0.289 at λ=0/0.5/1.0, nulls vanish at λ=0. The framework transfers off plasticity onto the L7-relevant COMPUTE axis | `artifacts/wp5-adaptive-compute-identifiability/` |
| AC2 learned compute-controller | reward-only controller recovers K=d | **SUPPORTED** — held-out worst-of-8 recovery 1.000, NULL 0.000, random<best_fixed. Compute-axis analog of L4a; closes AC1→AC2 (identifiability→learned controller) on the 2nd mechanism | `artifacts/wp5-adaptive-compute-controller/` |
| AC3 inferred-difficulty boundary | compute value bounded by I(C;Z) | **SUPPORTED** — noisy-difficulty sweep: recovery 1.0→0.0 monotone across I(C;Z) 1.585→0, vanishes at I=0, controller abstains. Master inequality quantitative on compute (compute analog of L4b) | `artifacts/wp5-adaptive-compute-inferred/` |
| AC4 compute rate-bridge | controller realises V*(R) | **SUPPORTED** — V_gov ≤ V*(I) everywhere, high-info saturation 0.971 (≥0.90 for I≥1 bit); low-info 0.326 documented (committed≠RI, widens with contexts). Closes AC1→AC2→AC3→AC4 = twin of L4→L4a→L4b→L4i | `artifacts/wp5-adaptive-compute-ratebridge/` |
| RD1 real-LM boundary (real data) | synthetic identifiability transfers to real LM | **NOT_SUPPORTED** — FROZEN NEGATIVE: on real byte-level prose, per-token compute allocation G_lo=−0.090 (gap ~0) while the synthetic positive control G_lo=+0.621. Maps the framework edge. *(The original "more compute helps all buckets uniformly" reading was later NARROWED by WP19 — that was a property of the weight-tied axis, not of the data.)* | `artifacts/wp6-real-lm/` |
| RIGOR1 certificate proof-gap closed | corrected bound valid + positives survive | **SUPPORTED** — proof-complete `b+2d` bound: Monte-Carlo FPR 0.000≤δ on 5 null families; every identifiability positive survives (L4 0.111→0.060, AC1 0.621→0.620). Closes the audit-flagged Proof caveat. Expert-class validity by construction | `artifacts/wp7-certificate-hardening/` |
| RIGOR2 family-wise error controlled | positives survive multiplicity correction | **SUPPORTED** — Bonferroni (family + ultra-conservative all-29) + Holm on top of the proof-complete bound: L4 G_lo +0.053/+0.029, AC1 +0.619, all survive. Family-wise FPR over SUPPORTED certificate positives ≤0.05. Closes the multiplicity critique | `artifacts/wp8-family-wise-error/` |
| RD3 real-workload pilot (2 task families) | a certifiable gap exceeds the MEASURED route cost on real workloads | **NOT_SUPPORTED** — ⛔ **KILL RULE FIRED**: prose G_lo −0.200, code −0.171 vs measured c_route 0.0006 (WP17); positive control +0.6195 certifies in the same run. 24 models, 2 families × 2 scales × 2 seq-lengths, 5 held-out eval shards each, contamination clean. **Architecture work stops by evidence, not budget** | `artifacts/wp18-real-workload-pilot/` |
| RD4 negative robustness (2nd compute axis) | the WP18 negative is robust across compute axes | **SUPPORTED_NARROWED** — untied-depth axis (18 independently trained models): the DECISION holds and strengthens (G_lo −0.484 / −0.234) but WP18's *explanation* is **falsified** — on real prose easy tokens prefer depth 2, harder tokens depth 3, so a genuine context×resource interaction DOES exist. Defensible claim: *the interaction is worth less than the decision costs* | `artifacts/wp19-negative-robustness/` |
| RIGOR10 timing metrology | Act G2 overhead p95 ≤2% and latency CV ≤3% are reachable | **NOT_SUPPORTED** — FROZEN NEGATIVE on this hardware: p95 4.87%/2.25%, CV up to 5.40%; median overhead 0.70% does pass. The gate flips between repeats, so the instrument requires pass-in-ALL. Hardware boundary, like energy | `artifacts/wp17-metrology/` |
| L5 structural plasticity | grow/prune/merge helps | **NOT_TESTED** | blocked |
| L6 joint-control advantage | joint > best isolated mechanism | **NOT_TESTED** | blocked |
| L7 compute-equivalent Pareto | beats MoD/MoE at equal budget | **NOT_TESTED** | cloud-blocked **and now evidence-blocked** — see `docs/publication/ASCENSION_ACT_STATUS.md` |
| L8 independent replication | third party reproduces | **NOT_TESTED** | not self-certifiable (a clean-room venv is not a different operator) |

Multiscale/fractal emergence: **NOT_SUPPORTED** (`artifacts/history/fractal/`,
INSUFFICIENT_EVIDENCE at the null gate).

## The load-bearing theory (`docs/IDENTIFIABILITY_THEORY.md`)
Oracle gap `G = 𝔼_c[max_a(β_a+γ_{c,a})] − max_a β_a` — the value of adaptive
control is *entirely* the context×choice interaction γ; a weakly-dominant
mechanism forces `G=0`. **Identifiability is a CONSTRAINED property**: quality
alone almost always has a dominant choice; adaptivity has value only when a hard
budget forbids using it everywhere. This explains all four negatives (weak
dominance) and both positives (routing v2, and the plasticity revival — gap
0.19 under a cost budget). Ships a cheap `O(|C||A|)` predictor to run on a pilot
before spending cloud compute (`scripts/identifiability_theory.py`).

**Empirical bridge — a trained controller realises V*(R)** (`experiments/act_j_pilot/`,
**EXPLORATORY / not preregistered / not a claim-ladder entry**): a real neural controller
(`context→P(a|c)`, MLP + Adam, GPU) trained on the rational-inattention objective
`E[U]−β·I(C;A)` converges to the analytic rate function `V*(I)` to machine precision across
all seeds/prices (`artifacts/act-j-pilot/`, verdict `TRAINED_CONTROLLER_REALISES_V_STAR`,
worst gap 0.0000; see `artifacts/act-j-pilot/verdict.json` for the honest caveat), and
exhibits the phase transition (at a high info price the critical problem routes, the regular
one abstains). This is a learning system **realising a KNOWN analytic fixed point** (a
fit-to-optimum convergence), NOT an independent empirical prediction; it closes the theory→
learning-system loop at runnable scale but is **not** in `claim_registry.json` and is **not**
the L7 Pareto (still cloud-blocked, and since WP18 also evidence-blocked).

**⭐ Information-market theory — one coherent synthesis** (`docs/INFORMATION_MARKET_SYNTHESIS.md`):
the map that ties the whole theory line into ONE object — the value-of-information rate
function `V*(R)` and its price `β=dV*/dR` — from the Landauer floor and neuron budget
through the master inequality, the Pinsker phase transition (regular Θ(R)/loose vs
critical Θ(√R)/tight, c=1 attained), the sharp rational-inattention solver, the economic
optimum `β(R*)=κ`, and the calibrated inference certificate, down to the single Act J
decision "spend iff `G_lo > c_route`". Start here for the theory.

**Unified value theory** (`docs/ADAPTIVE_COMPUTATION_VALUE_THEORY.md`): the oracle
gap, the Pinsker information bound, and the route-decision cost are three faces of
one master inequality `V_net ≤ min{ G(λ), Δu·√(I(C;Z)/2) } − c_route`. Adaptivity
pays only in the intersection of three admissible regions (no mechanism dominance,
enough signal information, decision cheaper than its value). Six theorems, each
proved and adversarially falsification-tested to ≈10⁻¹⁵ over 10⁴ random problems by
`experiments/common/adaptive_value_theory.py` (+ suite in `experiments/common/tests/`).
It is a *mathematical* scaffolding under L1/L2b/L2p — no new empirical claim.

**Inference breakthrough — calibrated pilot certificate** (`docs/IDENTIFIABILITY_INFERENCE.md`):
the step from converse-only ceilings to a decidable action. The oracle gap `G` is a
`max`-functional, so the plug-in estimate is upward-biased (Jensen) and the naive
`Ĝ>0` rule has an uncontrolled false-positive rate (up to 1.0 on a tied null). The
debiased one-sided bound `G_lo = Ĝ − sd√(2ln|A|) − (sd/√|C|)√(2ln(2/δ))` satisfies
`P(G≥G_lo)≥1−δ`: `G_lo>c_route` certifies positive value with FPR ≤ δ. Sample
complexity `n*=⌈(σK/G)²⌉`. This is the machine for deciding Act J spend with error
control (`experiments/common/identifiability_inference.py`).

**Pinsker phase transition** (`docs/VALUE_OF_INFORMATION_RATE_FUNCTION.md`): computes
the sharp value-of-information rate function `V*(R)=max{V(Z):I(C;Z)≤R}` the routability
ceiling only bounds, and proves *when* the ceiling is tight. Dichotomy at R→0: regular
problem (unique prior optimum) ⇒ `V*(R)=Θ(R)`, Pinsker asymptotically INFINITELY LOOSE;
critical problem (two actions tie — indifference manifold, measure zero) ⇒ `V*(R)=Θ(√R)`,
Pinsker asymptotically EXACT. So a routability certificate is conservative off the
indifference manifold — real routing headroom is smaller than the √I bound suggests.
Computed + falsification-tested (`experiments/common/value_of_information_rate.py`).

**Coherence & efficiency of the whole programme** (`docs/MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md`):
a machine-checked internal-consistency **audit** (Audit C — not a proof of coherence:
its utility matrices are hand-encoded stand-ins, so it catches a status mismatched to
its own encoded matrix but not a wrong matrix) that every recorded verdict equals the
sign of its theoretical certificate `Γ = min{G(λ), Δu√(I/2)} − c_route` — 0 contradictions
across the ladder; the three vetoes partition all negatives. Efficiency (Theorem E, a
genuine proof):
the identifiability predictor is `Θ(|C||A|)` and provably optimal (must read every
entry); measured `reads == |C||A|`. The auditor is falsifiable — it flags an injected
incoherent claim. `experiments/common/coherence_audit.py`.

**Physical substrate budget** (`docs/NEURON_INFORMATION_BUDGET.md`): a verified
biophysical model of the biological system CWC is modelled on — a cortical neuron
carries ≈10 bits/s (sensory up to ~150–300) at ≈2×10⁻¹⁰ W ⇒ ≈2×10⁸ ATP/bit ≈
10⁹–10¹⁰ Landauer floors. Non-linear network scaling: information saturates
(`I_∞=I_1/ρ`), energy is super-linear (wiring `N^α`), so bits/joule declines with
scale — the thermodynamic root of the route-decision cost. Three independent power
routes agree within ~15% (median); all draws respect the Landauer floor. Grounds the
master inequality in physics (`experiments/common/neuron_information_budget.py`).

**Route-decision-cost extension** (from `artifacts/wp2-routing-v3-*`): a positive
oracle gap is necessary but NOT sufficient for *usable* adaptive routing. The
controller must also be able to compute *which* mechanism is needed more cheaply
than just running the expensive one. Formally the realized value is
`G − c_route`, where `c_route` is the cost of the routing decision. On a
surface-matched benchmark the difficulty signal is a deep structural property
(`c_route ≈ c_expensive`), so even a supervised attention controller predicts the
route at chance and routing saves nothing — while on a surface-leaky benchmark
the same REINFORCE controller routes perfectly (`c_route ≈ 0`). The theory's
oracle gap must therefore be discounted by route-decision cost before any Pareto
claim.

## Directory map
```
cwc/instrumentation/   L0 measurement package (FLOPs, VRAM, energy, routing, evidence)
cwc/plasticity/        AMG core: registry + plasticity optimizer + SI/EWC/MAS importance
experiments/
  wp2_routing_v1/      frozen negative (ROUTER_COLLAPSE) — immutable
  wp2_mechanism_v2/    mechanism-separable routing (A2/A3 mechanism study)
  wp2_routing_v2/      typed semantic routing — ROUTING_CAUSALITY_SUPPORTED (narrowed);
                       also Routing v3 runners: runner_r3c_reinforce (end-to-end,
                       AUROC 1.0 under binding budget) + surface_matched_routing
                       (route-decision-cost boundary, ROUTE_DECISION_IS_THE_COMPUTATION)
  wp3_rcfr/            role-conditioned functional reuse — RCFR_NOT_SUPPORTED
  wp3_plasticity_v1/   metaplasticity oracle-gap — NOT_IDENTIFIABLE (unbudgeted)
  fractal_multiscale/  multiscale diagnostic — INSUFFICIENT_EVIDENCE (ARCHIVAL: sealed
                       frozen negative in artifacts/history/fractal/ with SHA256SUMS;
                       NOT in the live gate per "never recompute frozen negatives";
                       own harness needs py3.11+jsonschema, StrEnum shimmed for 3.10 import)
docs/                  protocols, contracts, audits, IDENTIFIABILITY_THEORY, vision/
artifacts/             one evidence bundle per experiment (RESULTS, verdict, SHA256SUMS)
  history/             immutable frozen negatives (wp1, wp2-routing-collapse, fractal)
scripts/               instrumentation, mutation probe, FLOP cross-check, theory
legacy/                archived predecessor (cognitive-weave-kernel), reference only
```

## Reproduce
```bash
make -f Makefile.cwc verify           # lint + types + tests + coverage + mutation + experiment tests
make -f Makefile.cwc verify-evidence  # checksum every evidence bundle
PYTHONPATH=. .venv/bin/python scripts/identifiability_theory.py   # the theory, from real data
```
Every experiment ships `artifacts/<exp>/{RESULTS.md, verdict.json, SHA256SUMS}`. Preregistration
discipline is honest about its own history: WP2-routing-v2 and RCFR have a `PREREGISTRATION.md`
that is a strict Git ancestor of their result commit; **WP4-adaptive-depth and Routing-v3
REINFORCE entered protocol+results in one commit and are therefore labeled
`RETROSPECTIVE_PROTOCOL`** (`docs/methodology/PREREGISTRATION_INTEGRITY_POLICY.md`,
`docs/vnv/DEBT_REGISTER_2026-07-19.md` T0-PREREG). The `act_j_pilot` is EXPLORATORY (not
preregistered). No positive is stated above the governance its provenance supports.

## Governing protocols (docs/)
`CWC_SEMANTIC_CONTRACT.md` (use/mention tiers), `DCSA_PROTOCOL_V2.md`
(evidence-gated audit), `RCFR_FALSIFICATION_CONTRACT.md`, `IDENTIFIABILITY_THEORY.md`.
Discipline: preregister before confirmatory runs (retrospective cases labeled
`RETROSPECTIVE_PROTOCOL`, not hidden); no claim above its gate; freeze negatives
immutably; energy is `INSTRUMENT_INVALID` on this hardware → excluded, and now
fail-closed in code (`enable_energy` requires `energy_instrument_invalid_ack`; a
<2-sample power window returns `available=False`, never a fabricated 0 J).

## The decisive next step
**Pilot run (`artifacts/act-j-pilot-decision/`, preregistered):** the §6
identifiability predictor + calibrated certificate was executed on the real
plasticity data. Verdict `PILOT_GO_L4_CONFIRMATORY` — debiased `G_lo = 0.081 > 0`
at `δ_eff = 0.0125` (Bonferroni over the λ grid), both negative controls refused,
positive control certified, certificate self-falsified. This green-lights the L4
cost-aware plasticity confirmatory run (freeze λ, charge `c_route`, fresh split); it
is **offline identifiability only** and does NOT touch L7. No local checkpoint ⇒ no
LM pilot; the L7 decision is still cloud-blocked.

Then **Act J** proper: compute-equivalent Pareto of the SUPPORTED routing controller
vs MoD / MoE / recursive baselines on ≥2 real workloads at cloud scale, then
independent replication. This is the only path from "causally-verified mechanism" to
"undeniable architectural result".

## Audit status
Stanford-grade checklist audit: `docs/CHECKLIST_STATUS.md` (+ .json). All four fundamental validity defects addressed locally; G0-G5 PASS/PARTIAL; G6-G8 cloud-blocked. Routing claim NARROWED (R-B value distillation; R-C autonomous collapses).

## Documentation-methodology system (Act CWC-LAB-DOC-2026-01)
Constitutional docs in `docs/methodology/` (master methodology, hypothesis registry,
protocol template, statistical analysis plan); data governance in `docs/data/`;
evaluation+metrology in `docs/evaluation/`; V&V traceability in `docs/vnv/` (RTM,
records, `DOCUMENT_STATUS_REGISTER.csv`); reproduction in `docs/reproducibility/`;
publication package in `docs/publication/`; System Card in `docs/system_card/`; risk
triggers in `docs/risk/`. Machine-verifiable spine: `scripts/doc_status_gate.py`
(claim⟷hypothesis 0 orphans, registry schema-valid, commit ancestor of HEAD, artifacts
exist) wired into `make -f Makefile.cwc verify`. Document register: **87 EXISTS / 0
MISSING / 10 TRIGGER_NOT_REACHED** (P2 frontier-safety deferred by the trigger ladder,
not fabricated). Deployment status: `LOCAL_RESEARCH_ONLY`.

**2026-07-22 — register de-drifted at the root.** The register was previously a
hard-coded list of 63 paths, so 34 of 72 documents on disk were untracked, including
`IDENTIFIABILITY_THEORY.md`, `ROUTABILITY_INFORMATION_BOUND.md`, `PROGRAMME_SUMMARY.md`
and `THREATS_TO_VALIDITY_AND_RED_TEAM.md`. `build_document_register.py` now emits
curated-governance entries **UNION a glob over `docs/`** (63 governed + 34 discovered =
97), closing the third and last instance of the hard-coded-gate-list class already killed
in `experiment-tests` and `verify-evidence`.

**Bibliography is now a gate, not a list.** `scripts/verify_bibliography.py` (offline,
inside `doc-gate`) enforces: every citation machine-resolved against an external
authority, BibTeX titles byte-identical to what the resolver returned, every reference
attached to a real `claim_registry.json` id, every reference argued in
`docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md`, and no dangling citations. 65
references, 0 unresolved. The review itself now records the **conceded overlaps** —
oracle gap = expected value of information, routability ceiling = Pinsker-type bound,
`V*(R)` = rational inattention — and the prior work reporting positive real-workload
adaptive-compute results that the RD1/RD2/RD3 negatives must confront.

## Provenance
Branch `wp1-instrumentation`, baseline `92d63d4e` (== upstream karpathy/nanochat,
verified pristine). Full backup: `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/`.

## ACT-R&D-02 research-operations boundary

The research plane now includes a fail-closed operational path:

`immutable source -> traceable claim -> hypothesis -> H4 design record -> compute governor -> preregistered run -> null/OOD -> sealed result -> H5 integration gate`.

Automation may generate candidates, code, nulls and measurements, but cannot self-grant causal truth or architecture authority. `C0 -> C1 -> C2 -> C3` escalation is enforced: expensive compute is rejected when a cheaper experiment can settle the current decision. Snapshot-only source material is quarantined rather than silently treated as full primary evidence.
