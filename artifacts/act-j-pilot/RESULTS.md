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

## It scales — machine precision at larger `|C|, |A|`

Random utility problems beyond 2×2 land on the analytic ceiling just as tightly
(β=0.3, seed 0):

| `|C|` | `|A|` | I trained | V trained | V*(I) | gap |
|---:|---:|---:|---:|---:|---:|
| 4 | 3 | 0.361 | 0.2054 | 0.2054 | 0.00000 |
| 6 | 4 | 0.536 | 0.3971 | 0.3971 | 0.00000 |
| 8 | 5 | 0.506 | 0.4411 | 0.4411 | 0.00000 |

Worst gap over the **entire** run (2 regimes × 3 seeds × 4 β + 3 scaling problems):
`8.4·10⁻⁷`.

## The phase transition, in a trained model

At a **high** information price (`β=3`): the *regular* controller acquires `I≈0` and
adds no value (routing does not pay) — while the *critical* controller acquires
`I=0.014` and captures `V=0.083` (routing always pays; the √R onset). This is the
theoretical dominance/√-onset dichotomy realised by gradient descent, not asserted.

## A noisy-sensor controller — bounded by the theory, and its inefficiency measured

A second controller sees only a **noisy observation** `O` of the context (symmetric
confusion channel, error `ε`) and learns `P(a|O)`. It converges to the Bayes value
`V(O)` — and the rate function bounds it, `V(O) ≤ V*(I(C;O))`:

| regime | ε | I(C;O) | trained V = V(O) | V*(I) | inefficiency `V*−V(O)` |
|---|---:|---:|---:|---:|---:|
| regular | 0.1 | 0.495 | 0.2125 | 0.2192 | 0.0067 |
| regular | 0.3 | 0.270 | 0.1375 | 0.1554 | 0.0179 |
| regular | 0.5 | 0.131 | 0.0625 | 0.0940 | 0.0315 |
| regular | 0.7 | 0.046 | 0.0000 | 0.0402 | 0.0402 |
| critical | any | — | = V*(I) | = V*(I) | **0.0000** |

The trained value matches `V(O)` exactly. **Correction (destruction stage):** the
symmetric confusion sensor is rate-optimal (inefficiency = 0) **iff the problem is
context-exchangeable** — invariant under the full permutation group on contexts (a
fully symmetric problem, at *any* `|C|`; verified for the `|C|=3` identity too). Being
merely *critical* (two tied actions) is **not** sufficient: a critical but
non-exchangeable problem (`[[1,0,0],[0,1,0],[½,½,0]]`) still leaves inefficiency
`0.05–0.10 > 0`. The earlier "rate-optimal for the critical problem" phrasing
over-generalised from 2×2 and is retracted. The inefficiency is the measurable *cost
of a channel not shaped to the (asymmetric) decision*.

## Compute-matched — the Act-J shape on the FLOP axis

The decisive question is value at **equal compute**. Each mechanism carries a FLOP cost
(`cheap=1, expensive=4`); an adaptive router trained under a compute price is compared to
the best context-blind policy spending the **same** average compute. Task: easy solved by
both, hard only by the expensive mechanism.

| regime | compute | adaptive V | static V | gap |
|---|---:|---:|---:|---:|
| identifiable (binding budget) | 1.00 (all cheap) | 0.500 | 0.500 | 0.000 |
| identifiable | **2.50** | **1.000** | **0.750** | **+0.250** |
| dominated (cheap solves all) | any | = static | = static | 0.000 |

At the binding budget the trained adaptive router **strictly dominates the static
frontier by 0.25 at equal FLOPs** — precisely the constrained oracle gap the theory
predicts (and the same 0.25 as budgeted routing-v2). When a mechanism weakly dominates,
routing buys **no** compute advantage (gap 0).

**General theorem (verified, `compute_matched_advantage`).** For *any* number of
mechanisms with arbitrary costs, the constrained oracle (adaptive) value is **never
below** the best context-blind (static) value at matched compute — because any static
policy is feasible for the adaptive fractional-knapsack LP. Adversarial check: 400
random problems with `|A|` up to 4, worst `adaptive − static = 0.000000`; the
`λ`-vertex concave-envelope oracle also dominates every pure per-context assignment. This is the compute-equivalent advantage
question (L7), answered at tiny synthetic scale and matching the theory exactly — a
proof of concept for the real Act J, not the cloud-scale result itself.

## On a REAL transformer — and its honest fragility (destruction stage)

The compute-matched idea was pushed onto a real trained transformer: follow a successor
pointer `h` times; easy (`h=1`) is solved at depth 3, hard (`h=3`) usually needs depth 4.
Adaptive spends depth 3 on easy, depth 4 on hard, vs a static depth policy at matched
average compute (3.5).

| seed | shallow acc on hard | adaptive @3.5 | static-matched @3.5 | gain |
|---:|---:|---:|---:|---:|
| 0 | **0.958** | 1.000 | 0.989 | **+0.011** |
| 1 | 0.411 | 1.000 | 0.853 | +0.147 |
| 2 | 0.210 | 0.999 | 0.802 | +0.197 |

**Honest finding:** adaptive depth is *never worse* than static at matched compute (by
construction, once both depths are trained to convergence — the deeper model trains
slower, so equal-step comparisons at too-few steps are unfair to it). But the strict
**advantage is not robust**: on seed 0 the shallow model *learned the hard task* (0.958),
the separation collapsed, and adaptivity bought almost nothing (+0.01). Mean gain +0.12,
min +0.01. Two earlier task designs (`h=1 vs 2`, `depth 2 vs 3`) were **retracted** —
they were not depth-separated at all once trained.

This mirrors the programme's own collapse findings (WP2 routing was bimodal): adaptive
computation pays exactly when the task is genuinely identifiable/separated, and whether a
transformer *is* separated at a given depth is a seed-dependent empirical accident, not a
promise. The clean, reproducible advantage lives in the decision-table experiment above;
the transformer shows the same principle **and its fragility** on a real model — the
destruction stage refusing to let a flaky positive stand.

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
