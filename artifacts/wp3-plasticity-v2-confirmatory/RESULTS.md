# L4 Plasticity Cost-Budget — CONFIRMATORY RESULTS

**Verdict: `L4_IDENTIFIABLE_CONFIRMED_SYNTHETIC`.** Preregistration:
`experiments/wp3_plasticity_v2_confirmatory/PREREGISTRATION.md` (committed before the run,
`λ=1` frozen a priori). Reproduce:
```
PYTHONPATH=. python -m experiments.wp3_plasticity_v1.src.runner_oracle --seeds 5..20 \
  --out artifacts/wp3-plasticity-v2-confirmatory/raw_runs
PYTHONPATH=. python -m experiments.wp3_plasticity_v2_confirmatory.src.analyze
```

## Out-of-sample confirmation

The cost-budget plasticity oracle gap was **discovered** on seeds 0–4 with `λ` chosen
post-hoc (exploratory). Here it is tested on **16 fresh held-out seeds (5–20)** with `λ=1`
**frozen before the run** — so no selection correction is needed and `δ=0.05` is applied
directly.

| Quantity | Value |
|---|---|
| Held-out seeds | 5…20 (n=16, disjoint from exploratory 0–4) |
| Frozen operating point | `λ = 1.0` (a priori) |
| Aggregate `Ĝ` (plug-in oracle gap) | **0.1909** |
| **`G_lo`** (debiased, one-sided, `δ=0.05`) | **0.1108** |
| max per-cell `se` (= σ/√16) | 0.0224 |
| **worst-seed gap** | **0.1903** |
| fraction of seeds with `G_s > 0` | **1.00 (16/16)** |
| `c_route` (given-task) / headroom | 0.0 / **0.1108** |

`G_lo = 0.1108 > c_route = 0` at `δ=0.05`: the mechanism is **identifiable
out-of-sample**. The effect is present in **every** held-out seed (worst 0.1903 ≈ mean
0.1909 — the gap is essentially seed-invariant), so it is not an in-sample or selection
artifact. `G_lo` here (0.111) is even tighter than the pilot's (0.081) because n=16
shrinks the standard error.

## Mechanism (why the gap is real)

Under a hard parameter-cost budget the oracle allocates the **cheap** `head` group
(cost 512) to *lexical* — which `head` already solves (acc 1.0) — and reserves the
**expensive** `attn` group (cost 4096) for *relational*, which is structurally solvable
only by `attn`. No single fixed group wins both under the budget; the context-conditioned
allocation does. This is the interaction `γ` the identifiability theory predicts pays only
under a binding budget.

## Controls (the run can fail — these arms behave)

| Control | expected | result |
|---|---|---|
| NEG_A weak-interaction (`λ=0`, same 16 seeds) | not identifiable | `G_lo ≤ 0` ✓ |
| NEG_B quality-dominance (routing plug-in gap) | not identifiable | `G_lo ≤ 0` ✓ |
| POS specialization `[[1,0],[0,1]]` at run noise | identifiable | `G_lo > 0` ✓ |
| certificate self-falsification | valid | `all_ok=True` ✓ |

## Scope (tier `SYNTHETIC`)

Confirms L4 identifiability on the toy GroupedModel benchmark under an exact oracle. It
does **NOT** establish: a learned governor achieves the gap, compute-equivalent Pareto
(L7), energy/latency advantage, real-workload generalization, or independent replication.
Registry advance: `CWC-L4-plasticity` → **`SUPPORTED_NARROWED`** (synthetic, oracle, no
learned controller). The next real step remains L7 (cloud) or a learned-governor study.
