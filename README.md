# Cognitive Wiring Core (CWC)

> **Fork notice.** This repository is a fork of
> [github.com/karpathy/nanochat](https://github.com/karpathy/nanochat) (MIT License —
> full credit to Andrej Karpathy and nanochat's contributors for the base
> implementation; the `master`/`baseline` branches here are the unmodified upstream
> history). The original contribution in this repository — Cognitive Wiring Core
> (CWC) / Sapolsky-behavioral-layers research — is by Yaroslav Vasylenko, primarily on
> the `wp1-instrumentation` branch (this GitLab project's default branch). See
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

The bibliography is machine-verified, not hand-written: all 65 references were resolved
against external authorities (arXiv API, DOI content negotiation, OpenAlex, Open Library),
the resolution record is
[`docs/publication/BIBLIOGRAPHY_VERIFICATION.json`](docs/publication/BIBLIOGRAPHY_VERIFICATION.json),
and `make -f Makefile.cwc bib-gate` fails if any citation is unresolved, hand-altered,
attached to a claim id that does not exist, or never argued.

## Reproduce

```bash
uv sync --frozen                                     # hermetic environment from uv.lock
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
