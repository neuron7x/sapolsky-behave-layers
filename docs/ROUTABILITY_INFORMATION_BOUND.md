# The Routability Bound: When Adaptation Cannot Pay

Let `C` be latent context, `Z` the router-visible signal, `A` an action, and
`u(c,a) ∈ [u_min,u_max]`. Define the value of observing `Z`:

```
V(Z) = E_Z max_a E[u(C,a)|Z] - max_a E[u(C,a)].
```

With `Δu=u_max-u_min` and mutual information in nats,

```
0 ≤ V(Z) ≤ Δu · E_Z TV(P(C|Z),P(C))
          ≤ Δu · sqrt(I(C;Z)/2).
```

Therefore, if routing costs `c_route`,

```
Δu · sqrt(I(C;Z)/2) ≤ c_route  =>  V_net ≤ 0.
```

No optimizer or extra training can overcome this certificate without changing the
accessible signal, utility range, or cost model.

## Proof

The informed policy can ignore `Z`, so `V(Z)≥0`. At each `z`, improvement over the
prior-optimal action is at most
`sup_a |E_{P(C|z)}u_a-E_{P(C)}u_a|`, which is bounded by
`Δu·TV(P(C|z),P(C))`. Average over `z`; Pinsker bounds TV by the square root of
conditional KL, and Jensen moves the expectation outside the concave square root.
Mean conditional KL is `I(C;Z)`. Subtract `c_route`. □

| Oracle gap | Cheap-signal information | Consequence |
|---|---|---|
| zero | any | adaptation has no task value |
| positive | zero | value exists but is unroutable |
| positive | insufficient for cost | provably non-positive net value |
| positive | sufficient | possible, not guaranteed; train and intervene |

The bound is one-sided and can be loose. Empirical MI can be biased: publication use
requires uncertainty bounds and direct interventions. The dependency-free verifier in
`experiments/common/value_information.py` is tested on an exhaustive finite grid and
1,000 deterministic adversarial random decision problems.

> **Adaptive computation is an information market: buy information about difficulty
> only when its maximum decision value exceeds its acquisition cost.**

## Prior art and provenance (added 2026-07-22)

Every step of this bound is classical. Recording that here is not modesty, it is the
scope of the claim.

| Step | Established source |
|---|---|
| `V(Z) ≥ 0` and value-of-information framing | Howard, *Information Value Theory* (1966) — `V(Z)` relative to a context-blind policy is expected value of information |
| `TV` bound on the per-`z` improvement | standard; see Cover & Thomas, *Elements of Information Theory* |
| `TV ≤ √(KL/2)` | Pinsker-type inequality; Kullback (1967), *A lower bound for discrimination information in terms of variation* |
| Jensen step to `√(I(C;Z)/2)` | standard |
| behaviour of an optimal decision-maker under an information constraint | Sims (2003), rational inattention; Ortega & Braun (2013), information-processing costs |

**What CWC therefore claims here: nothing new.** The contribution attached to this
document is not the inequality but its use as an *executable, cost-charged decision
gate* — `c_route` is physically measured (WP17) and charged inside the certificate, and
the resulting screen is falsification-tested (`CWC-R1-routability-screen`). Full
citations, arguments and the conceded overlaps:
[`docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md`](publication/RELATED_WORK_AND_NOVELTY_REVIEW.md) §2.5,
machine-verified in [`docs/publication/BIBLIOGRAPHY_VERIFICATION.json`](publication/BIBLIOGRAPHY_VERIFICATION.json).
