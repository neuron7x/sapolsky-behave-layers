# Act-J Pilot — a trained neural controller realises the analytic V*(R)

**Verdict: `TRAINED_CONTROLLER_REALISES_V_STAR`.** Worst gap to theory over the full
sweep (2 regimes × 3 seeds × 4 information prices β): **0.0000**.

## What was run

A real neural controller (`context → P(a|c)`, 2-hidden-layer GELU MLP, Adam) is trained
by gradient descent on the exact rational-inattention objective
`E_c[Σ_a P(a|c)U[c,a]] − β·I(C;A)` — the same Lagrangian whose analytic optimum is the
value-of-information rate function `V*(R)` (`experiments/common/value_of_information_rate.py`,
the Matějka–McKay fixed point). Trained on a single GPU (torch 2.9, CUDA); ~1m50s for
the full run (`experiments/act_j_pilot/src/runner.py`).

## Result — the trained network reaches the theoretical ceiling

For every `β`, the converged `(I, V)` of the trained controller lands on `V*(I)` to
machine precision. Representative (seed 0):

| regime | β | I trained | V trained | V*(I) analytic | gap |
|---|---:|---:|---:|---:|---:|
| regular `[[1,0],[0,½]]` | 3.0 | 0.000 | −0.000 | 0.000 | 0.0000 |
| regular | 0.3 | 0.355 | 0.184 | 0.184 | 0.0000 |
| regular | 0.1 | 0.673 | 0.248 (=G) | 0.248 | 0.0000 |
| critical `[[1,0],[0,1]]` | 3.0 | 0.014 | 0.083 | 0.083 | 0.0000 |
| critical | 0.3 | 0.543 | 0.466 | 0.466 | 0.0000 |
| critical | 0.1 | 0.693 | 0.500 (=G) | 0.500 | 0.0000 |

## The phase transition, in a trained model

At a **high** information price (`β=3`): the *regular* controller acquires `I≈0` and
adds no value (routing does not pay) — while the *critical* controller acquires
`I=0.014` and captures `V=0.083` (routing always pays; the √R onset). This is the
theoretical dominance/√-onset dichotomy realised by gradient descent, not asserted.

## Reproduce

```bash
PYTHONPATH=. python experiments/act_j_pilot/src/runner.py --out artifacts/act-j-pilot
PYTHONPATH=. python -m pytest -q experiments/act_j_pilot/tests/   # fast deterministic check
```

## Scope

Synthetic decision problems (2×2), oracle controller (clean context). It validates that
a *trained* controller realises the analytic ceiling and shows the phase transition — it
is **not** a compute-equivalent Pareto result against MoD/MoE on a real workload
(`CWC-L7-pareto: NOT_TESTED`). It is the empirical bridge from the theory to a learning
system, at the scale this hardware runs.
