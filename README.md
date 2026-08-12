# Cognitive Wiring Core (CWC)

> **Fork notice.** This repository is a fork of
> [github.com/karpathy/nanochat](https://github.com/karpathy/nanochat) (MIT License —
> full credit to Andrej Karpathy and nanochat's contributors for the base
> implementation; the upstream baseline is preserved in this repository's history.
> The original contribution in this repository — Cognitive Wiring Core (CWC) /
> Sapolsky-behavioral-layers research — is by Yaroslav Vasylenko. The canonical,
> consolidated research state is published from the `main` branch. See
> [`CITATION.cff`](CITATION.cff) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
> for full attribution detail.

An **evidence-first research programme** investigating whether a causally-controlled
adaptive-computation architecture beats static Transformers / MoE / dynamic-compute
systems at equal budget. This repository is the laboratory: a verified measurement
substrate, a falsification harness, preregistered experiments, immutable evidence
bundles, and a mathematical theory that unifies the results.

> **What this is (honest one-line).** A verified instrumentation substrate + a
> falsification harness that has produced **claim-tier positives and negatives** plus
> a **mathematical theory** that predicts them. It is **not** yet an architecture with
> a proven Pareto advantage at scale, and makes no such claim.

Full map and entry point: [`SYSTEM.md`](SYSTEM.md). Governing methodology:
[`docs/methodology/CWC_MASTER_METHODOLOGY.md`](docs/methodology/CWC_MASTER_METHODOLOGY.md).
This project is built on top of Andrej Karpathy's **nanochat** (see
[`docs/upstream/NANOCHAT_README.md`](docs/upstream/NANOCHAT_README.md)); the CWC work is
additive and the upstream baseline is recorded pristine.

## Headline results (claim-tier, reproducible)

| Result | Verdict | Evidence |
|---|---|---|
| Instrumentation is deterministic & internally validated | **SUPPORTED** | `artifacts/wp1-release/` (207 tests, 99.46% cov, 12/12 mutation) |
| A benchmark with a real adaptive-compute advantage exists | **SUPPORTED** | `artifacts/wp2-routing-v2/` (oracle gap 99.8%) |
| Synthetic halt-oracle identity: adaptive−static = `P_sample(m>K)` | **SUPPORTED_NARROWED** | `artifacts/wp4-adaptive-depth/`; interpretation corrected in `docs/vnv/EPISTEMIC_CORRECTION_WP4_2026-07-19.md` |
| Frozen exact operator-hop allocation with free halt oracle | **SUPPORTED_NARROWED_INTERNAL** | `artifacts/wp4-exact-compute-v31/`; 16 untouched seeds, 7 distributions; not end-to-end compute parity |
| End-to-end routing is learnable once credit-assignment is fixed | **SUPPORTED (binding budget)** | `artifacts/wp2-routing-v3-r3c-reinforce/` (AUROC 1.0, 8 seeds) |
| On a surface-matched task the route decision IS the computation | **ROUTE_DECISION_IS_THE_COMPUTATION** | `artifacts/wp2-routing-v3-surface-matched/` |
| Functional reuse (RCFR) is novel | **NOT_SUPPORTED** (ties prior art) | `artifacts/wp3-rcfr/` |
| Metaplasticity benchmark identifiable unbudgeted | **NOT_TESTED / non-identifiable** | `artifacts/wp3-plasticity-v1/` |
| Multiscale/fractal emergence | **NOT_SUPPORTED** | `artifacts/history/fractal/` |

The unifying theory (`docs/IDENTIFIABILITY_THEORY.md`): the value of adaptive control
is the context×choice interaction `γ`, realized only under a **binding budget** and
only when the route signal is **cheaply computable** — `V_realized = oracle_gap − route_decision_cost`.

## What CWC does NOT claim

- ❌ a compute-equivalent Pareto advantage over MoD/MoE at scale (**NOT_TESTED** — cloud);
- ❌ energy efficiency (energy is `INSTRUMENT_INVALID` on this hardware, excluded);
- ❌ autonomous general adaptive intelligence;
- ❌ independent replication (**NOT_TESTED** — not self-certifiable);
- ❌ any frontier / deployment-grade capability.
- ❌ an exactly compute-matched WP4 Pareto result (the archived static budget is
  `round(E_sample[m])`, while adaptive compute is `E_sample[m]`).

See the full non-claim boundary in [`SYSTEM.md`](SYSTEM.md) and per-claim scope in
[`claim_registry.json`](claim_registry.json).

## Novelty boundary — what is actually original here

The mechanisms are not. Adaptive halting, adaptive depth, learned routing and
importance-weighted plasticity are established prior art, and the value-of-information
theory this repository builds on is classical: the oracle gap is expected value of
information (Howard, 1966), the routability ceiling is a Pinsker-type bound (Kullback,
1967), and the `V*(R)` frontier is rational inattention (Sims, 2003). Those overlaps are
conceded in writing, per claim, in
[`docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md`](docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md) §3 —
including the prior work that reports *positive* real-workload results this programme's
negatives must confront (§2.3).

> **The one defensible novelty statement:** not a mechanism and not a theory, but an
> **executable, falsification-tested instrument that decides — before spending — whether a
> given workload can pay for adaptivity**, together with the frozen negatives that
> instrument produced when turned on its author's own preferred hypothesis.

The bibliography is machine-verified, not hand-written: all 70 references were resolved
against external authorities (arXiv API, DOI content negotiation, OpenAlex, Open Library),
the resolution record is
[`docs/publication/BIBLIOGRAPHY_VERIFICATION.json`](docs/publication/BIBLIOGRAPHY_VERIFICATION.json),
and `make -f Makefile.cwc bib-gate` fails if any citation is unresolved, hand-altered,
attached to a claim id that does not exist, or never argued.

## Reproduce

```bash
uv sync --frozen --extra cpu                         # runtime environment from uv.lock
make -f Makefile.cwc install-dev                     # exact-pinned CWC verification tooling
make -f Makefile.cwc verify                          # lint + types + tests + coverage + mutation + experiments
make -f Makefile.cwc verify-evidence                 # checksum every evidence bundle
make -f Makefile.cwc reproduce-primary               # re-derive the primary result end-to-end
```

Every experiment ships `artifacts/<exp>/{RESULTS.md, verdict.json, SHA256SUMS}` and a
`experiments/<exp>/PREREGISTRATION*.md` committed before its confirmatory run.

## Repository status

- **Deployment status:** `LOCAL_RESEARCH_ONLY` — not a public service, not safety-critical,
  not autonomously deployed, no frontier-capability claim. See
  [`docs/system_card/CWC_SYSTEM_CARD.md`](docs/system_card/CWC_SYSTEM_CARD.md).
- **Academic-readiness:** internal evidence substrate STRONG; academic documentation system
  in progress — see [`docs/CHECKLIST_STATUS.md`](docs/CHECKLIST_STATUS.md) and the document
  register [`docs/vnv/DOCUMENT_STATUS_REGISTER.csv`](docs/vnv/DOCUMENT_STATUS_REGISTER.csv).

## License & citation

MIT ([`LICENSE`](LICENSE)). Third-party components: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
To cite, use [`CITATION.cff`](CITATION.cff).

### R&D-02 status (2026-08-10)

The repository now contains an executable research-operations substrate (`cwc/research_ops/`) and the preregistered `CSCA-01` controlled causal-credit experiment. CSCA-01 reproduced the exact counterfactual-credit kernel on controlled OOD/null tests, but **does not** authorize architecture integration: the source remains primary-bytes-quarantined, the counterfactual simulator is oracle-quality, real-model utility is untested, and H5 human integration review is pending. See `research/reports/ACT_RD_02_EXECUTION_REPORT.md`.


### CSCA-06A falsifiability status (2026-08-10)

The first blockwise composite-null interventional falsifier is preserved as a preregistered negative (`PRIMARY S2=120/128=0.9375 < 0.95`). A separately preregistered repair, `CSCA-06A-R1`, aggregates evidence globally at exactly three fixed cost checkpoints and, on fresh cohorts, rejects S1/S2/S3 `128/128` in both PRIMARY and independent REPLICATION while rejecting none of N0-N3/E0. This is **composite model-class falsification under a declared nuisance envelope**, not graph-truth identification. Hidden-confounder and aleatoric variance remain non-identifiable from the scalar intervention channel, and no shadow/replay/active-control promotion follows.


### CSCA-06B/06C real-model boundary (2026-08-10)

Two explicit same-context donor-resampling soft-intervention kernels give identical exact top/sign credit on every fresh CSCA-06B PRIMARY and replication prompt, but all 96 robust cases choose `A_RECENT`. CSCA-06C then cyclically moves the same four candidate contents through all four positions while freezing the base next-token target. Every fully resolved case follows fixed position (`PositionTracking=1.0`) rather than moved content (`ContentTracking=0.25`); however independent-replication resolution coverage falls below the frozen gate (PROSE 0.333, pooled 0.458). Therefore content-specific causal credit is **NOT_SUPPORTED**, while position/locality remains unpromoted. No student, replay, semantic or active-control authority follows.


### CSCA-07 passive replay boundary (2026-08-10)

Passive factual traces can now falsify a declared predictive replay law with an anytime-valid e-process, but cannot silently certify latent causal truth. CSCA-07 includes exact observational-equivalence counterexamples: identical observed dynamics and Jacobian spectra with different latent topology, a stable invariant hidden replay attractor with zero observational information, and zero within-model fiber entropy with unresolved model semantics. Causal/replay/active authority remains blocked without separately justified identifying assumptions.


### CSCA-08 assumption-typed regime boundary (2026-08-11)

A synthetic multi-regime IV-style identifying contract now separates some observable assumption violations from high aleatoric noise and weak information while carrying unresolved assumptions as runtime debt. Both fresh PRIMARY and REPLICATION cohorts passed the frozen gate. The decisive negative is preserved: coordinated direct regime effects can be pathwise observationally equivalent to a different causal coefficient, so the system emits only `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`, never unconditional causal truth. Real-trace exogeneity/exclusion, replay control and active control remain blocked.

### COG-EPISTEMIC-01R typed authority boundary (2026-08-11)

CWC now has an immutable capability-bound runtime state machine: `OBSERVED -> PREDICTIVE -> ASSUMPTION_CONDITIONAL -> INTERVENTION_SUPPORTED`, with absorbing `UNIDENTIFIED/FALSIFIED/OOD/ABSTAIN` states. A fresh repaired confirmatory run rejected every frozen illegal promotion (`0/1536` PRIMARY and `0/1536` REPLICATION) while accepting every legal chain (`128/128` each). The parent run remains preserved as non-passing because one stochastic F11 precondition was never reached. `INTERVENTION_SUPPORTED` is explicitly scoped to its operator/context and is not semantic or unconditional causal truth. Next gate: assumption-aware memory consolidation.

### COG-MEMORY-01 assumption-aware memory boundary (2026-08-11)

CWC now binds reusable memory to the exact typed epistemic record, assumptions,
evidence hashes, countermodel set, dependencies and revision lineage. Assumption-
conditional memories remain quarantined; surviving countermodels veto active causal
consolidation; parent retraction and assumption invalidation propagate transitively.
PRIMARY and fresh REPLICATION passed all 12 frozen families at 128/128 with zero false
causal consolidation. This is a runtime safety primitive, not proof of semantic causal
truth or planning/replay value. Next hard gate: proof-carrying counterfactual planning.

### COG-PLAN-01 proof-carrying planning boundary (2026-08-11)

CWC now carries epistemic uncertainty through memory into action selection. A
`ROBUST_ACTION` requires the same margin-separated action in every admitted world;
world disagreement triggers certified information acquisition or abstention rather
than hidden averaging. Assumption-conditional memory remains conditional, surviving
countermodels must be represented, and memory/world mutations invalidate old plan
certificates. PRIMARY and fresh REPLICATION passed all 12 frozen families at 128/128.
This is a synthetic planning-safety primitive, not proof of real-world planning value
or causal truth.


### COG-INFO-02 decision-relevant information boundary (2026-08-11)

CWC now separates causal-model identification from immediate decision identification.
Surviving worlds are partitioned by the action they imply; same-decision worlds remain
explicit causal uncertainty but cannot waste or veto evidence acquisition for that action.
Across 12 frozen synthetic families, PRIMARY and fresh REPLICATION passed 128/128 per
family. A same-decision zero-rate world blocked the legacy model-maximin governor in
256/256 pooled cases while the decision-relevant governor still selected the decisive
probe; when both could acquire, the D11 necessary-cost bound improved in 256/256 cases
(median legacy/new ratio 9.7754x). This is an information-allocation primitive only,
with novelty explicitly UNKNOWN and real-world/active-control authority blocked.


### COG-SELF-01 autonomous falsification boundary (2026-08-11)

CWC now composes typed authority, dependency-aware memory, proof-carrying planning and
decision-relevant information allocation into a bounded self-falsification governor. An
attack is admissible only when it can discriminate action-flipping worlds and is bound to
the current plan's transitive load-bearing memory/assumption graph. PRIMARY and fresh
REPLICATION each passed all 12 frozen families at 128/128 with zero false spend, stale
plan acceptance, irrelevant/uncertified attack selection, survival promotion or
stale/unbound outcome acceptance. Negative outcomes may only retract/invalidate bound
authority; survival cannot self-promote. This remains a synthetic runtime primitive. The
next hard gate is public/real-model matched-compute external validity, not another private
synthetic module.
