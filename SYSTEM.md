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
| L2 routing causality | learned controller routes causally, beats all controls | **SUPPORTED** | `artifacts/wp2-routing-v2/` bal 1.0, NMI 1.0, AUROC 1.0, CRE 1813×, 8 seeds |
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

## Directory map
```
cwc/instrumentation/   L0 measurement package (FLOPs, VRAM, energy, routing, evidence)
cwc/plasticity/        AMG core: registry + plasticity optimizer + SI/EWC/MAS importance
experiments/
  wp2_routing_v1/      frozen negative (ROUTER_COLLAPSE) — immutable
  wp2_mechanism_v2/    mechanism-separable routing (A2/A3 mechanism study)
  wp2_routing_v2/      typed semantic routing — ROUTING_CAUSALITY_SUPPORTED
  wp3_rcfr/            role-conditioned functional reuse — RCFR_NOT_SUPPORTED
  wp3_plasticity_v1/   metaplasticity oracle-gap — NOT_IDENTIFIABLE (unbudgeted)
  fractal_multiscale/  multiscale diagnostic — INSUFFICIENT_EVIDENCE
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

## Provenance
Branch `wp1-instrumentation`, baseline `92d63d4e` (== upstream karpathy/nanochat,
verified pristine). Full backup: `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/`.
