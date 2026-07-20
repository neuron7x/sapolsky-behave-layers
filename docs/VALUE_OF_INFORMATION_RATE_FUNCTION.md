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

The general constant is now pinned exactly. At *any* two-action critical point (actions
`a,b` tie, `D := U[·,a]−U[·,b]`, `𝔼_p D = 0`), the small-rate value is
`V(Z) = ½·𝔼_z|𝔼[D|Z=z]|`, and its rate-constrained optimum is

> **Theorem 4‴ (general critical constant).**
> `V*(R) = √( R·Var_p(D)/2 )·(1+o(1))`, so the leading coefficient is
> `κ = std_p(D)/√2` and the Pinsker-ratio limit is
> `c = std_p(D)/Δu ≤ 1`, with equality iff `|D| = Δu` almost surely.

*Verified* (`critical_leading_constant`): the formula predicts the RI-solved
`V*(R)/√R` and `V*(R)/(Δu√(R/2))` to `2·10⁻³` on symmetric and asymmetric criticals
(`c = 1.00, 0.47, 0.43`), and `c=1` **iff** the tie is symmetric. This is the sharpest
statement of *how* tight the routability bound is on the whole indifference manifold:
the attainment factor is the standard deviation of the tied-action utility gap, in
units of the utility range.

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

### 4b. The sharp general solver (rational inattention)

The binary-signal grid is only a *lower* bound on `V*` once `|A|>2`. The sharp value
for any finite `|C|,|A|` comes from recognising that

> `max_channel [ V(Z) − β·I(C;Z) ]` **is the rational-inattention problem**
> (Sims; Matějka–McKay 2015): the Shannon-information-cost decision problem.

Its optimum is the fixed point `P(a|c) ∝ P(a)·exp(U[c,a]/β)`,
`P(a)=Σ_c p_c P(a|c)`, solved by a convergent Blahut–Arimoto-style iteration.

> **Why this is the GLOBAL optimum (not a local one).** `I(C;A)` is *convex* in the
> channel `{P(a|c)}` for a fixed input `p(c)` (Cover–Thomas Thm 2.7.4), and `E[U]` is
> linear, so `E[U] − β·I` is **concave** for `β>0` — its stationary point is the unique
> global maximum. By the revelation principle any richer signal `Z` satisfies
> `I(C;A) ≤ I(C;Z)` for the induced optimal action `A`, at equal value, so restricting
> the signal to an action-recommendation is without loss; hence the RI trace equals
> `V*(R)` exactly. This is a proof, not an assumption — and it is why `V*(R)` is concave
> (its slope `β(R)` is the multiplier, which decreases as the constraint relaxes).
> *Destruction-stage check:* over 1200 random `(problem, R)` points the RI value never
> undershoots the independent grid solver (worst `grid − RI = 0.00000`) and never
> exceeds the envelope — the concavity proof and the numerics agree exactly.
`I(β)` is decreasing in the shadow price `β`; bisecting `β` to hit `I(β)=R` yields the
exact `V*(R)` (`optimal_value_at_rate_ri`). It is **cross-validated three ways**: it
reproduces the closed-form symmetric-critical value to machine precision (`1.7·10⁻¹⁶`),
matches the exact binary grid solver, and **strictly exceeds** the binary-signal lower
bound at `|C|=|A|=3` (`0.081 > 0.075` at `R=0.02`) — finding the optimal *stochastic*
channel the grid cannot resolve. With it the phase-transition exponents sharpen to
`0.97` (regular) and `0.498` (critical). The value of information under a Shannon cost
is exactly the routing-market price of §0, now computed sharply at any scale.

### 4c. The marginal value of a nat — and the fractal link to energy

The rational-inattention shadow price is the **marginal value of information**
`β(R) = dV*/dR` [utility per nat] (`marginal_value_of_information`), verified to equal
the numerical derivative of `V*`. Because `β` is a Lagrange multiplier it is
**decreasing in `R`**, so `V*` is **concave** (settling Prop 1 rigorously); it is
finite as `R→0` at a regular problem (the information sensitivity `σ`) and **diverges**
at a critical one (the √R onset, seen from the derivative side).

`β` closes the loop with `NEURON_INFORMATION_BUDGET.md`. A physical router pays `β`
utility per nat, and by Landauer every nat costs at least `k_B T` joules to acquire
irreversibly, so

> **decision value per joule ≤ β / (k_B T)** (`utility_per_joule_ceiling`).

The same information-market price — `min{value, cost}` at §0, `β = dV*/dR` here — now
in physical units, from the abstract decision down to the biological substrate. The
market is fractal: it prices a bit the same way at the routing gate and at the ion
channel, and the exchange rate `β/(k_B T)` is where the two scales meet.

### 4d. The economic optimum — how much to route

With a per-nat acquisition cost `κ`, the net value of a routing decision is
`V*(R) − κR`. Because `V*` is concave with decreasing slope `β(R)`, the optimum is the
classical **marginal-value = marginal-cost** condition (`optimal_information_budget`):

> **Theorem 4″ (optimal information budget).** The net-optimal amount of information
> to acquire is `R*` solving `β(R*) = κ`, and routing pays at all iff the first nat
> clears its cost, `β(0⁺) > κ`:
> * **regular** (`β(0⁺)=σ` finite): route iff `κ < σ` — the *information sensitivity*
>   is the exact routing threshold;
> * **critical** (`β(0⁺)=∞`): **always** acquire a positive `R*` — the first nat is
>   infinitely valuable, so any finite cost is worth paying.

*Verified:* at the optimum `β(R*)=κ` to bisection precision; `V*(R*)−κR*` exceeds the
net value at neighbouring rates; a regular problem routes below `σ` and refuses above
`2σ`; a critical problem routes for every finite `κ`. This is the operational payoff of
the whole rate-function theory — it turns "how tight is Pinsker?" into "exactly how many
bits of difficulty-signal to buy, and whether to buy any." For Act J: estimate `κ` (the
learned route-decision cost) and the pilot utility matrix, then read off `R*` and the
certified net value before committing cloud compute.

## 4e. Application — the budget tunes CWC routing-v2 to near-criticality

Applying the apparatus to the real routing-v2 experiment closes the loop. The budgeted
utility (`λ=0.5`) is `EASY=[1, 0.5]`, `HARD=[0.004, 0.5]`; the prior-optimal action
(direct) wins by a **margin of only 0.002** — routing-v2 sits *right next to the
indifference manifold*, yet is strongly identifiable (`G = 0.248`). Consequently the
marginal value of a difficulty-signal is **amplified ~17×** (`β(10⁻⁴) ≈ 17.6` versus
`≈1.05` for a generic regular problem): near criticality the value is in the √R regime,
where a *little* signal is worth a lot and Pinsker is near-tight.

So the binding budget does more than make routing identifiable (§4 of
`IDENTIFIABILITY_THEORY.md`): it places the problem at the **most
information-efficient** operating point, which is why budgeted routing-v2 showed both a
positive oracle gap *and* a large empirical CE gap — and why it routes profitably even
at a substantial route-decision cost (`optimal_information_budget` returns `route=True`
up to `κ=5`). The theory now *explains* the empirical result rather than merely bounding it.

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
* The sharp `V*` is now available for **general `|C|,|A|`** via the rational-inattention
  solver (§4b), cross-validated against the closed form and the grid; the binary grid and
  binary-signal grid remain as independent checks. The exact leading constant `c` is
  pinned on the *symmetric* indifference locus (§4, `c=1`); the constant on the whole
  indifference manifold as a function of local geometry remains the natural next target.

## Relationship to sibling documents

* `ROUTABILITY_INFORMATION_BOUND.md` — proves the ceiling; this note says when it binds.
* `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` — Theorems 3–4 give the envelope; Props 4.1–4.2 drive the critical case.
* `MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md` — the certificate `Γ` uses the ceiling `V*` sharpens.
