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
| L4 controlled plasticity | budgeted metaplasticity oracle gap is real | **SUPPORTED_NARROWED** — cost-budget oracle gap confirmed OUT-OF-SAMPLE on 16 held-out seeds with λ frozen a priori: G_lo 0.111>0 (δ=0.05), effect in 16/16 seeds, controls pass; synthetic + oracle, NO learned governor | `artifacts/wp3-plasticity-v2-confirmatory/` (confirmatory); `artifacts/wp3-plasticity-v1/` unbudgeted null + `artifacts/act-j-pilot-decision/` pilot |
| L5 structural plasticity | grow/prune/merge helps | **NOT_TESTED** | blocked |
| L6 joint-control advantage | joint > best isolated mechanism | **NOT_TESTED** | blocked |
| L7 compute-equivalent Pareto | beats MoD/MoE at equal budget | **NOT_TESTED** | **the decisive next step (cloud)** |
| L8 independent replication | third party reproduces | **NOT_TESTED** | not self-certifiable |

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
the L7 Pareto (still cloud-blocked).

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
exist) wired into `make -f Makefile.cwc verify`. Document register: **53 EXISTS / 0
MISSING / 10 TRIGGER_NOT_REACHED** (P2 frontier-safety deferred by the trigger ladder,
not fabricated). Deployment status: `LOCAL_RESEARCH_ONLY`.

## Provenance
Branch `wp1-instrumentation`, baseline `92d63d4e` (== upstream karpathy/nanochat,
verified pristine). Full backup: `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/`.
