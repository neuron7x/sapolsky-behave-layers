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

**Sharpest result** (`artifacts/wp4-adaptive-depth/`): the first narrow causal
mechanism whose advantage cannot be explained by static architecture, capacity,
or optimization — adaptive allocation of a fixed compute budget beats the best
static allocation by *exactly* `P(m>K)`, predicted from the task's difficulty
distribution before the run, confirmed to machine precision (max error 0.0000)
over 8 seeds × 4 regimes, beating input-blind random depth at equal compute.

## Claim ladder — current state
| Level | Claim | Status | Evidence |
|---|---|---|---|
| L0 measurement substrate | instrumentation deterministic & validated | **SUPPORTED** | `artifacts/wp1-release/`, 207 tests, 99.46% cov, 12/12 mutation |
| L1 benchmark identifiability | a benchmark with a real adaptive-compute advantage exists | **SUPPORTED** | `artifacts/wp2-routing-v2/` oracle gap 99.8% |
| L2 routing causality | learned controller routes causally, beats all controls | **SUPPORTED (NARROWED)** — under counterfactual value distillation, label-derived test capacity, surface cues present, no physical compute saving; see `artifacts/wp2-routing-v2/claim_boundary.json` | `artifacts/wp2-routing-v2/` bal 1.0, NMI 1.0, AUROC 1.0, 8 seeds |
| L2a end-to-end routing (leaky benchmark) | leakage-free-*target* controller routes without value distillation | **SUPPORTED under a binding budget** — the earlier straight-through *collapse* was an estimator artifact; a REINFORCE controller (L=L_task+λ·C_use) reaches AUROC 1.0 with NO privileged target / NO label-derived capacity — but only at λ≥1 (binding budget), and surface cues are still present | `artifacts/wp2-routing-v3-r3c-reinforce/` learned 0.009 vs random 0.48, 8 seeds |
| L2b route-decision cost (surface-matched) | can a cheap controller route when difficulty is purely structural? | **NO — ROUTE_DECISION_IS_THE_COMPUTATION** | `artifacts/wp2-routing-v3-surface-matched/` — on a surface-matched task neither a cheap nor an attention controller routes above chance (AUROC ~0.51, no loss saving) even under *direct supervision*; predicting the route costs ~the expensive computation |
| L2′ adaptive-compute Jensen gap | adaptive allocation beats best static by exactly P(m>K), not capacity/compute/optimization | **SUPPORTED** | `artifacts/wp4-adaptive-depth/` gap=P(m>K) to 0.0000, 8 seeds × 4 regimes, beats random |
| L3 functional reuse (RCFR) | one module = many functions, novel | **NOT_SUPPORTED** | `artifacts/wp3-rcfr/` — real but ties DISeL (prior art) |
| L4 controlled plasticity | budgeted metaplasticity governor helps | **NOT_TESTED** | `artifacts/wp3-plasticity-v1/` — benchmark not identifiable UNBUDGETED (see theory) |
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
Every experiment has `artifacts/<exp>/{RESULTS.md, verdict.json, SHA256SUMS}` and
`experiments/<exp>/PREREGISTRATION.md` committed before its confirmatory run.

## Governing protocols (docs/)
`CWC_SEMANTIC_CONTRACT.md` (use/mention tiers), `DCSA_PROTOCOL_V2.md`
(evidence-gated audit), `RCFR_FALSIFICATION_CONTRACT.md`, `IDENTIFIABILITY_THEORY.md`.
Discipline: preregister before confirmatory runs; no claim above its gate; freeze
negatives immutably; energy is `INSTRUMENT_INVALID` on this hardware → excluded.

## The decisive next step
Run the §6 identifiability predictor on a small pilot, then **Act J**:
compute-equivalent Pareto of the SUPPORTED routing controller vs MoD / MoE /
recursive baselines on ≥2 real workloads at cloud scale, then independent
replication. This is the only path from "causally-verified mechanism" to
"undeniable architectural result".

## Audit status
Stanford-grade checklist audit: `docs/CHECKLIST_STATUS.md` (+ .json). All four fundamental validity defects addressed locally; G0-G5 PASS/PARTIAL; G6-G8 cloud-blocked. Routing claim NARROWED (R-B value distillation; R-C autonomous collapses).

## Provenance
Branch `wp1-instrumentation`, baseline `92d63d4e` (== upstream karpathy/nanochat,
verified pristine). Full backup: `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/`.
