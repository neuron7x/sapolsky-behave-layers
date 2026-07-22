# CWC Programme Summary — A Falsification-Disciplined Theory of Adaptive-Computation Value

*Expert-reviewable synthesis. Everything below is committed, gated, checksummed, and reproduced by
`make -f Makefile.cwc verify`. Entry map: [`SYSTEM.md`](../../SYSTEM.md). Claim ledger:
[`claim_registry.json`](../../claim_registry.json). Adversarial review:
[`THREATS_TO_VALIDITY_AND_RED_TEAM.md`](THREATS_TO_VALIDITY_AND_RED_TEAM.md).*

## 1. What the programme is (and is not)

A **value-of-information theory of adaptive computation** — when does spending a variable resource
(which parameters to adapt; how much compute) *by context under a budget* beat any fixed policy? —
validated on **two independent real trained mechanisms**, statistically hardened to expert grade,
and honestly bounded by a real-data negative. It is **not** an architecture and makes **no**
compute-equivalent-Pareto claim (that is L7, cloud-blocked).

## 2. The theory

- Oracle gap `G = 𝔼_c max_a(β_a+γ_{c,a}) − max_a β_a`: value of adaptation = the context×choice
  interaction `γ`, realised only under a binding budget (Theorems 1–5 — **genuine proofs**).
- Value-of-information rate function `V*(R)` and the master inequality
  `V_net ≤ min{G(λ), Δu√(I/2)} − c_route`.
- Calibrated pilot certificate `G_lo` deciding "spend iff `G_lo > c_route`" with FPR ≤ δ, now
  **proof-complete** (WP7) and **family-wise-error controlled** (WP8).

## 3. Two real mechanism arcs (structural twins)

| rung | parameter-plasticity | adaptive-compute |
|---|---|---|
| identifiable | L4 (`SUPPORTED_NARROWED`) | AC1 (`SUPPORTED`) |
| learned controller recovers it | L4a | AC2 |
| value bounded by `I(C;Z)` | L4b | AC3 |
| realises `V*(R)` | L4i | AC4 |
| mechanism characterization | L4c/d/e/f | — |
| robustness / generalization | L4g/h | — |
| foundation nulls | L4k | — |

One theory governs both. The compute axis is the L7-relevant one; identifiability, a learned
controller, an information-bounded value, and rate-function saturation all transfer to it.

## 4. Expert-class statistical hardening (WP7–WP13)

- **WP7** — proof-complete certificate (`b+2d`), FPR ≤ δ Monte-Carlo, positives survive.
- **WP8** — family-wise error: Bonferroni (all-30) + Holm; positives survive.
- **WP9** — independence assumption **not load-bearing** (coverage robust to `ρ=0.9` correlation).
- **WP10** — de-circularized coherence: status ↔ certificate sign from **real artifacts**, both
  directions, 0 contradictions.
- **WP11** — Pinsker dichotomy certified over a **random sample** (regular ≈1, critical ≈0.5), not
  four curated instances.
- **WP12** — preregistration integrity: 14 experiments `STRICT_ANCESTOR`; same-commit only if
  disclosed (the gate caught this run's own batching and we disclosed it).
- **WP13** — effect sizes + bootstrap 95% CIs strictly above zero + retrospective power.

## 5. The honest boundary and the frozen negatives

The real-data axis was tested **three independent times**, each stronger than the last, and it is
now the boundary that governs the whole programme:

| WP | design | result |
|---|---|---|
| **WP6** | unigram difficulty, 66 KB prose | `G_lo = −0.09` (control `+0.62`) — not identifiable |
| **WP14** | bigram difficulty, same corpus | not identifiable — robust to the difficulty signal |
| **WP18** | **2 task families** (prose + Python), 1.07 MB, hash-split with 5 held-out eval shards each, 2 scales × 2 sequence lengths, 24 models | `G_lo = −0.200 / −0.171` vs **measured** `c_route = 0.0006` → **kill rule fired** |
| **WP19** | same workloads on an **untied-depth** compute axis, 18 models | `G_lo = −0.484 / −0.234` — decision **reinforced**, but the *explanation* falsified (below) |

**The kill rule of the ascension act fired at WP18: architecture work stops.** Not because of cloud
cost, but because at reachable scale no real workload shows a compute-allocation gap that exceeds
the *physically measured* cost of making the routing decision (WP17).

**WP19 is the part worth reading.** It attacked this programme-halting negative and **falsified the
author's own explanation of it**. WP18 had claimed "there is no context × resource interaction on
real data — every difficulty bucket wants the same compute". On an untied-depth axis that is
**false**: on real prose, easy tokens are best served by depth 2 and harder tokens by depth 3. A
genuine interaction exists. What survived is the *decision*, on both axes and both workloads:

> The defensible statement is **not** "there is no interaction on real data" — that is false —
> but **"the interaction is worth less than the decision costs."**

- Ten `NOT_SUPPORTED` claims (L2c, L3, L4c, L4d, L4e, fractal, RD1, RD2, RD3, RIGOR10) — the
  `(σ/Δ)²` law fails, the collapse is drift-limited, RCFR ties prior art, real-data identifiability
  is absent on two signals and two task families, and the Act's timing-metrology spec is not
  reachable on the available hardware. The negatives are what make the positives credible.

## 6. Ledger

42 claims / 42 hypotheses, all preregistered (or disclosed-retrospective), gated, checksummed,
`verify-full` GREEN, on GitLab. 25 `SUPPORTED`, 5 `SUPPORTED_NARROWED`, 10 `NOT_SUPPORTED`,
2 `NOT_TESTED` (L7 cloud, L8 replication). Preregistration integrity is machine-audited: 18
strict-ancestor, 5 disclosed-retrospective, **0 violations**.

## 7. Reproducibility capsule

```bash
uv sync --frozen                        # fresh env from the pinned lock
make -f Makefile.cwc verify-full        # gates + evidence checksums + primary reproduced
```
`verify-full` is the single canonical command (WP16). It was executed in a **clean-room venv built
from `uv.lock --frozen`, independent of the author's environment**: 9/9 gates pass and
`reproduce-primary` regenerates the primary verdict from scratch. Machine-readable record with
host/GPU/CUDA/timings and skip **reason codes**: `artifacts/wp16-cleanroom-release/`. Hardware-gated
tests are recorded `NOT_MEASURED`, never `PASS`. Every analysis is deterministic given committed raw
seeds; every utility is frozen and checksummed.

## 8. The decisive next step — and why it is *not* L7 any more

Until WP18 the answer was "spend on L7". **It no longer is.** The ascension act's own pilot
instrument was built precisely to decide whether to spend cloud budget, and its verdict is
**do not spend yet**: on two real task families, two compute axes, two model scales and two
sequence lengths, the certified gap never exceeds the measured route-decision cost.

L7 (compute-equivalent Pareto vs MoD/MoE at scale) and L8 (independent replication) remain
`NOT_TESTED`. They are now gated behind a **prior** question, which is the honest next step:

> **Find a real workload whose context × resource interaction is large enough to pay for its own
> routing decision.** Everything downstream — strong baselines, causal controller, sparse
> execution, the Pareto trial — is unfalsifiable ceremony until such a workload exists.

Candidate directions (none attempted here, all beyond a 4 GB consumer GPU): tasks with genuinely
heterogeneous per-instance difficulty (multi-step reasoning, retrieval-conditioned generation,
mixed-modality batches) rather than per-token byte prediction, where the compute demand of an
instance varies by orders of magnitude rather than by ~0.001 nats.
