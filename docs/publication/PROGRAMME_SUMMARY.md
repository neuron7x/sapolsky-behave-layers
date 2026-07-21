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

- **WP6** — the clean identifiability does **not** transfer to real language-model per-token
  difficulty (`G_lo=−0.09`; positive control `+0.62`). The sharp interaction is a property of the
  synthetic benchmarks.
- Seven `NOT_SUPPORTED` claims (L2c, L3, L4c, L4d, L4e, fractal, RD1) — the `(σ/Δ)²` law fails, the
  collapse is drift-limited, RCFR ties prior art, real-data identifiability is absent. The negatives
  are what make the positives credible.

## 6. Ledger

35 claims / 35 hypotheses, all preregistered (or disclosed-retrospective), gated, checksummed,
`verify` GREEN, on GitLab. ≈18 `SUPPORTED`, 4 `SUPPORTED_NARROWED`, 7 `NOT_SUPPORTED`, 2 `NOT_TESTED`
(L7 cloud, L8 replication).

## 7. Reproducibility capsule

```bash
uv sync --frozen
make -f Makefile.cwc verify            # lint+types+tests+coverage+mutation+experiment-tests+gates
make -f Makefile.cwc verify-evidence   # checksum every evidence bundle
```
Every analysis is deterministic given committed raw seeds; every utility is frozen and checksummed;
every verdict reproduces. A third party can replicate via
`docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md`.

## 8. The one decisive next step

**L7** — compute-equivalent Pareto of the identified mechanisms vs MoD/MoE on ≥2 real workloads at
cloud scale, then independent replication (L8). Everything here is the strongest locally-provable
case and decision instrument *for* L7 — WP6 shows it does not come free — but it is not L7.
