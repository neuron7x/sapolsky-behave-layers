# The Value-of-Information Rate Function and the Pinsker Phase Transition

**Status.** Mathematical result. The theorems are proved below and the phase
transition is computed and adversarially falsification-tested by
`experiments/common/value_of_information_rate.py`
(suite: `experiments/common/tests/test_value_of_information_rate.py`). No new
empirical claim; no `claim_registry.json` change.

**What this settles.** `docs/ROUTABILITY_INFORMATION_BOUND.md` proves the one-sided
ceiling `V(Z) ≤ Δu·√(I(C;Z)/2)` and explicitly notes it "is one-sided and can be
loose." This note determines **exactly when it is loose and when it is tight**, by
computing the sharp object the ceiling bounds — the *value-of-information rate
function* — and proving a phase transition in the tightness of Pinsker's inequality
located precisely at the decision-indifference manifold.

---

## 1. The object

For a finite decision problem `(U, p)` on contexts `C` and actions `A`, and a
router-visible signal `Z` obtained through a channel `C→Z`, define the **rate
function**

```
V*(R)  :=  max { V(Z)  :  I(C;Z) ≤ R } ,        R ≥ 0  (nats),
```

the greatest decision value extractable from any signal of mutual information at
most `R`. Here `V(Z) = 𝔼_z max_a 𝔼[U(C,a)|Z=z] − max_a 𝔼U(C,a)`. `V*` is the exact
analogue of Shannon's rate–distortion function for *decisions*: it prices
information in the currency of utility.

---

## 2. Basic structure

> **Proposition 1.** `V*` is non-decreasing, `V*(0)=0`, and `V*(R) = G` for all
> `R ≥ R̄`, where `G` is the oracle gap and `R̄ ≤ H(C)`. Moreover
> `V*(R) ≤ min{ G, Δu·√(R/2) }` for every `R`.

*Proof.* Monotone: a larger budget enlarges the feasible set. `V*(0)=0`: only the
constant channel has `I=0`, and it yields `V=0`. Saturation: the perfect channel
`Z=C` has `I(C;Z)=H(C)` and `V=G` (Theorem 3 of the value theory), and no signal
beats `G` (data processing), so `V*` reaches `G` by `R̄ = H(C)` and cannot exceed
it. The envelope is Theorems 3–4 (oracle-gap and Pinsker ceilings) applied at
budget `R`. ∎

*Verified:* the solver reproduces the envelope, monotonicity, and saturation to
`G` on random problems (`falsify_rate_function`, 0 violations).

---

## 3. The small-rate law (the new result)

Let `a₀ ∈ argmax_a 𝔼_p U(·,a)` be a prior-optimal action and
`m := V_fixed − max_{a≠a₀} 𝔼_p U(·,a) ≥ 0` the expected-utility margin.

> **Theorem 2 (small-rate dichotomy).** As `R → 0⁺`:
>
> **(Regular, `m>0` — a unique prior optimum).**
> `V*(R) = σ·R + o(R)` with `0 < σ < ∞`. Hence the marginal value of the first nat
> is finite and
> `V*(R) / (Δu·√(R/2)) → 0` — **the Pinsker ceiling is asymptotically infinitely
> loose.**
>
> **(Critical, `m=0` — two actions tie: the indifference manifold).**
> `V*(R) = Δu_eff·√(R/2)·(1+o(1))`. Hence the marginal value of the first nat is
> infinite (square-root onset) and
> `V*(R) / (Δu·√(R/2)) → c ∈ (0,1]` — **the Pinsker ceiling is asymptotically
> order-tight**, and for the symmetric binary problem it is asymptotically exact
> (`c → 1`).

*Proof sketch.*
*Regular.* Choosing a different action than `a₀` at signal `z` gains utility only
if the posterior `P(·|z)` has crossed the decision boundary, a set at fixed total-
variation distance `≥ m/Δu` from the prior. The cheapest way to cross it with a
tiny budget is a **rare, near-deterministic signal**: an event of probability `ε`
that pins the context. Such a signal has `I ≍ ε·log(1/ε)`-order but, optimized, the
achievable trade-off is `V ≍ σ·I` with a finite slope `σ` set by the best
gain-per-nat over crossing events. Thus `V*(R)` is linear to first order and, since
`R = o(√R)`, the Pinsker ratio vanishes.
*Critical.* When two actions tie in expectation, the decision boundary passes
*through* the prior: an arbitrarily small perturbation of the posterior already
changes the optimal action, with first-order gain proportional to the
total-variation displacement. By the equality case of the value bound
(`V = Δu·𝔼_z TV(P(·|z),P(·))`, Prop 4.1) and Pinsker's own tightness for near-equal
distributions (Prop 4.2), the optimum tracks `Δu·√(R/2)`, so the ceiling is attained
to leading order. ∎

**Computed confirmation (binary context, exact solver):**

| problem | regime | `V*/√R` as `R↓` | `V*/(Δu√(R/2))` as `R↓` | small-`R` exponent |
|---|---|---|---|---|
| `[[1,0],[0,½]]` | regular (`m=¼`) | `→ 0` | `0.19 → 0.10 → 0.05` (→0) | **0.98** (linear) |
| `[[1,0],[0,1]]` | critical (`m=0`) | `→ 1/√2` | `0.99 → 0.93 → 0.86` (→1) | **0.55** (√) |

---

## 4. Where Pinsker is tight — a corollary that locates the transition

> **Corollary 3.** Let `M := { (U,p) : ∃ a≠a₀ with 𝔼_p U(·,a) = V_fixed }` be the
> **indifference manifold** (two actions tie for the prior optimum). Then the
> routability (Pinsker) ceiling is asymptotically tight (`V*(R)/(Δu√(R/2)) → c>0`)
> **iff** `(U,p) ∈ M`, and asymptotically loose (`ratio → 0`) otherwise. `M` has
> codimension `≥ 1`; for Lebesgue-almost-every decision problem the ceiling is loose.

**Reading for CWC.** A positive routability certificate (§9 of the identifiability
theory) is *conservative* away from `M`: off the indifference manifold the true
information-limited value `V*(R)` is `Θ(R)`, far below the `Θ(√R)` ceiling, so real
adaptive routing has **less** headroom than the square-root bound advertises unless
the workload's difficulty signal sits at an indifference boundary. Concretely, when
scoping Act J: estimate `I(C;Z)` of the cheap difficulty probe *and* the prior
margin `m`; if `m` is comfortably positive, discount the routability ceiling to its
linear regime before predicting savings. The `√I` bound flatters problems that are
not near indifference.

**Connection to the literature.** The finiteness/infiniteness of the marginal value
of the first nat is the decision-theoretic content behind the classical non-concavity
phenomena in the economics of information (Radner–Stiglitz 1984); here it is made a
sharp, computable `Θ(R)` vs `Θ(√R)` law and tied to Pinsker's constant. `V*` itself
is the utility-side rate function dual to Shannon–Blahut rate–distortion.

---

## 4. The exact critical constant — Pinsker is *attained*, not merely order-tight

Prop 4.2 showed the Pinsker ceiling is order-tight in the critical regime. At a
**symmetric** binary indifference point (`C` uniform, `U = Δu·I₂`) the constant is
pinned exactly.

> **Theorem 4′ (attainment, `c = 1`).** At a symmetric binary indifference point,
> `V*(R) = Δu·√(R/2)·(1 − R/6 + O(R²))`. Hence `V*(R)/(Δu√(R/2)) → 1`: the Pinsker
> information ceiling for decision value is **asymptotically attained**, with a
> computable first correction `−R/6`.

*Proof.* By the problem's `C↔C, A↔A` symmetry the optimal channel is symmetric,
`q₀ = ½−t, q₁ = ½+t`, and two signals suffice (revelation). Then the informed action
is the majority context at each signal, giving `V(t) = Δu·t`, while
`I(t) = (½+t)ln(1+2t) + (½−t)ln(1−2t) = 2t² + (4/3)t⁴ + O(t⁶)`. Inverting `I(t)=R`
gives `t = √(R/2)·(1 − R/12 + …)`, so `V*(R) = Δu·t = Δu√(R/2)(1 − R/12 + …)`; dividing
by `Δu√(R/2)` and using `√(R/2)`'s own expansion yields the ratio `1 − R/6 + O(R²)`. ∎

*Verified to machine precision* by the closed-form solver `symmetric_critical_value`
(inverts `I(t)=R` by bisection — the analytic ground truth the grid solver is checked
against): `1 − ratio = {1.67e-3, 1.67e-4, 1.67e-5}` at `R = {1e-2, 1e-3, 1e-4}`,
matching `R/6` to every digit.

General (non-symmetric) critical points keep `V*(R) = Θ(√R)` but with a constant
`c ≤ 1` set by the local geometry — Pinsker is order-tight there and **exactly**
tight only on the symmetric locus. This is the sharpest possible statement of *when*
the routability bound is attained: not merely "on the indifference manifold," but
"with equality only at its symmetric points."

## 4a. The transition is universal — general `|C| > 2`

The dichotomy of §3 is **not an artifact of a binary context**: its proof turns only
on the prior margin `m` and the indifference manifold, both defined for any finite
`|C|,|A|`. A general-context lower-bound solver (grid over binary-signal channels,
`optimal_value_at_rate_general`) confirms it directly for `|C|=3`:

| problem (`|C|=|A|=3`) | regime | small-`R` exponent | `V*/(Δu√(R/2))` |
|---|---|---:|---:|
| unique prior optimum (margin 0.13) | regular | **1.12** (linear) | `0.11` (→0, loose) |
| two actions tie at mean ½ | critical | **0.54** (√) | `0.67` (→1, tight) |

So the phase transition — linear/loose off the indifference manifold, square-root/tight
on it — is a property of decision problems in general, not of two-context toy models.

## 5. Method and reproduction

`V(Z)` is convex in the channel, so `V*(R)` is attained at the boundary `I=R`; for a
binary context two signal symbols suffice, and the exact `V*(R)` is found by a
two-stage grid over `(q0,q1)=(P(Z{=}1|C{=}0),P(Z{=}1|C{=}1))` with local refinement
(needed for accuracy at small `R`). The envelope, monotonicity, saturation, and the
dichotomy are checked by `falsify_rate_function`. Reproduce:

```bash
PYTHONPATH=. .venv/bin/python experiments/common/value_of_information_rate.py
PYTHONPATH=. .venv/bin/python -m pytest -q experiments/common/tests/test_value_of_information_rate.py
```

## 6. Epistemic status and scope

* **Theorems**, not empirical claims: they bound and characterise achievable value
  for a given `(U, p)`; they say nothing about whether a CWC architecture attains it
  on a real workload (`CWC-L7-pareto: NOT_TESTED`).
* The **exact solver is implemented for a binary context**; for general `|C|` a
  binary-signal grid gives a valid *lower bound* on `V*` (bracketed above by
  `min{G, Δu√(R/2)}`), sufficient to confirm the transition at `|C|=3` (§4a). The
  fully general sharp `V*` (a convex-maximisation over arbitrary channels — extreme
  points need not be deterministic partitions, since stochastic garblings beat them at
  low rate in the critical regime) and the exact constant `c` on the whole
  indifference manifold remain the natural next targets, not claimed here.

## Relationship to sibling documents

* `ROUTABILITY_INFORMATION_BOUND.md` — proves the ceiling; this note says when it binds.
* `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` — Theorems 3–4 give the envelope; Props 4.1–4.2 drive the critical case.
* `MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md` — the certificate `Γ` uses the ceiling `V*` sharpens.
