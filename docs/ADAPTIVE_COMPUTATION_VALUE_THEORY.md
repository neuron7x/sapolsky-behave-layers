# A Unified Value Theory of Adaptive Computation

**Status.** Mathematical note. Every theorem below is proved, and each is
*independently re-derived and adversarially falsification-tested* to machine
precision by `experiments/common/adaptive_value_theory.py` (10⁴ random decision
problems, worst violation ≈ 1.8·10⁻¹⁵) with the suite
`experiments/common/tests/test_adaptive_value_theory.py`. These are theorems about
*value*; they bound what any adaptive controller can achieve. They are **not**
empirical claims about the CWC system and add no entry to `claim_registry.json`.

**Why this note exists.** Three prior CWC results were, until now, stated as three
separate facts: the oracle-gap identifiability theory (`IDENTIFIABILITY_THEORY.md`
§1–8), the route-decision-cost discount (`IDENTIFIABILITY_THEORY.md` §9), and the
Pinsker information bound (`ROUTABILITY_INFORMATION_BOUND.md`). This note proves
they are three faces of one inequality (Theorem 6) and supplies the two pieces the
earlier notes left informal: an **exact `⇔` characterisation** of when adaptivity
has zero value (Theorem 2, strengthening the two one-directional corollaries), and
a **bounded identifiability window** with an explicit cost-saturation threshold
(Theorem 5).

---

## 0. Standing assumptions and notation

Let `C` be a finite context set, `A` a finite action/mechanism set, and
`Z` a finite router-visible signal. Fix:

* a context law `p ∈ Δ(C)` (`p_c ≥ 0`, `Σ_c p_c = 1`);
* a bounded utility `U : C × A → ℝ` (write `U[c,a]`), with **range**
  `Δu := max_{c,a} U[c,a] − min_{c,a} U[c,a]`;
* for the routing results, a joint law `π ∈ Δ(C × Z)` with marginals `p_c`, `p_z`;
* for the budgeted results, a cost `K : A → ℝ_{≥0}` and a Lagrange multiplier
  `λ ≥ 0`.

All quantities are finite sums; no measure-theoretic machinery is needed. Mutual
information `I(C;Z)` is in **nats** (natural logarithm), which fixes the Pinsker
constant at `1/2` throughout.

### The four value functionals

```
V_oracle      := Σ_c p_c · max_a U[c,a]                (perfect context, per-context choice)
V_fixed       := max_a Σ_c p_c · U[c,a]                (best context-blind constant policy)
G             := V_oracle − V_fixed                    (oracle gap = value of a free, perfect view)
V(Z)          := Σ_z p_z · max_a E[U(C,a) | Z=z]  −  max_a E[U(C,a)]   (value of the actual signal)
V_net         := V(Z) − c_route                        (realised value after paying the routing tax)
```

`G` is the ceiling under a *free, perfect* view of `C`; `V(Z)` is the value under a
*finite, noisy* signal `Z`; `V_net` charges the computational cost `c_route ≥ 0` of
actually deciding the route.

---

## 1. Oracle gap: decomposition and non-negativity

> **Theorem 1.** Write the weighted two-way ANOVA
> `U[c,a] = μ + α_c + β_a + γ[c,a]` with `Σ_a γ[c,a] = 0` and `Σ_c p_c γ[c,a] = 0`.
> Then
> `G = 𝔼_{c∼p}[ max_a ( β_a + γ[c,a] ) ] − max_a β_a`, and `G ≥ 0`.

*Proof.* The main effects are the orthogonal projections
`μ = Σ_c p_c ⟨U[c,·]⟩_a`, `α_c = ⟨U[c,·]⟩_a − μ`,
`β_a = Σ_c p_c U[c,a] − μ`, where `⟨·⟩_a` is the uniform mean over `A`; `γ` is the
residual, and the two zero-sum constraints hold by construction. Because
`Σ_c p_c γ[c,a] = 0`, `Σ_c p_c U[c,a] = μ + β_a`, so `V_fixed = μ + max_a β_a`.
Because `Σ_c p_c α_c = 0`,
`V_oracle = μ + Σ_c p_c α_c + 𝔼_c[max_a(β_a+γ[c,a])] = μ + 𝔼_c[max_a(β_a+γ[c,a])]`.
Subtract. Non-negativity is Jensen applied to the convex map
`v ↦ max_a v_a`: `𝔼_c max_a U[c,a] ≥ max_a 𝔼_c U[c,a]`. ∎

**Corollary 1.1 (interaction drives everything).** If `γ ≡ 0` then `G = 0`: main
effects `β` never create a gap; only the context×choice interaction can.

*Verified:* `oracle_gap` returns both `gap` and `gap_via_anova` and asserts they
agree (`gap_matches_decomposition`); the identity holds to ≈10⁻¹⁵ over 3·10³
random matrices (`test_decomposition_identity_and_nonnegativity_random`), and
`test_zero_interaction_forces_zero_gap` pins Corollary 1.1.

---

## 2. The exact zero-value characterisation

The earlier note gave two *sufficient* conditions for `G = 0` (γ ≡ 0; a weakly
dominant action). They are in fact the **same** condition, and it is also
**necessary**.

> **Theorem 2 (dominance ⇔ zero gap).** `G = 0` **iff** some action `a★` is
> *weakly optimal in every context of positive mass*:
> `U[c,a★] = max_{a} U[c,a]` for all `c` with `p_c > 0`.

*Proof.* (⇐) If such `a★` exists then
`V_fixed ≥ Σ_c p_c U[c,a★] = Σ_c p_c max_a U[c,a] = V_oracle`, and `G ≥ 0` gives
`G = 0`. (⇒) If `G = 0` then some maximiser `a★` of `Σ_c p_c U[c,a]` attains
`Σ_c p_c U[c,a★] = V_oracle = Σ_c p_c max_a U[c,a]`. Since `U[c,a★] ≤ max_a U[c,a]`
pointwise and the two `p`-weighted sums are equal, the integrand must agree on
every `c` with `p_c > 0`. ∎

**Interpretation.** Adaptivity has *exactly zero* value precisely when one fixed
mechanism is already as good as the per-context optimum everywhere it matters — the
"weakly-dominant mechanism" regime that explains all four CWC negatives. There is
no third way for the gap to vanish.

*Verified:* `oracle_gap` exposes `weakly_dominant` and `gap_is_zero`; the harness
counts any disagreement as a `dominance_iff_failure` and finds **0** over 10⁴
problems; `test_weak_dominance_iff_zero_gap_random` runs 5·10³ integer-utility
matrices (frequent exact ties, so both branches fire).

---

## 3. Data-processing ceiling: a noisy signal cannot beat the oracle

> **Theorem 3 (`0 ≤ V(Z) ≤ G`).** For any joint law of `(C,Z)`, the value of the
> router-visible signal is non-negative and never exceeds the oracle gap on the
> true context.

*Proof.* Non-negativity: the informed policy may ignore `Z`, so
`Σ_z p_z max_a E[U|z] ≥ max_a Σ_z p_z E[U|z] = max_a E U`, giving `V(Z) ≥ 0`.
Upper bound: for each `z`, `max_a E[U(C,a)|z] ≤ E[max_a U(C,a) | z]` (the max of
conditional means is at most the conditional mean of the max). Averaging over `z`,
`Σ_z p_z max_a E[U|z] ≤ 𝔼_c max_a U[c,a] = V_oracle`. Subtract the common term
`max_a E U = V_fixed`. ∎

This is the value-theoretic form of the data-processing / Blackwell principle: no
router reading a garbled `Z` can extract more decision value than an oracle that
sees `C` itself. Equality holds when `Z` determines `C` (a perfect signal).

*Verified:* `signal_value` reports `data_processing_holds`; the harness worst
violation is ≈10⁻¹⁵; `test_perfect_signal_attains_oracle_gap` pins the equality
case `V(Z)=G=0.5`.

---

## 4. Information ceiling and its sharpness

> **Theorem 4 (sharp Pinsker ceiling).**
> `V(Z) ≤ Δu · 𝔼_z TV( P(C|z), P(C) ) ≤ Δu · √( I(C;Z) / 2 )`, with `I` in nats.

*Proof.* At each `z`, and for any action `a`, the informed policy's edge over the
prior-optimal action is at most
`sup_a | E_{P(C|z)}U(·,a) − E_{P(C)}U(·,a) |`. Because a signed measure of total
variation `TV` moves mass of total size `TV` across a utility spread of at most
`Δu`, this is `≤ Δu · TV(P(C|z),P(C))`. Average over `z` for the first inequality.
Pinsker gives `TV(P(C|z),P(C)) ≤ √( KL(P(C|z) ‖ P(C)) / 2 )`; Jensen moves `𝔼_z`
inside the concave `√`; and `𝔼_z KL(P(C|z) ‖ P(C)) = I(C;Z)`. ∎

> **Proposition 4.1 (TV step is tight).** For a binary context and the indicator
> utility `U = [[1,0],[0,1]]`, `V(Z) = Δu · 𝔼_z TV(P(C|z),P(C))` exactly: the
> first inequality is an equality, so no constant below `1` multiplies the TV term.

> **Proposition 4.2 (rate and constant are optimal).** For the symmetric binary
> channel `Z = C ⊕ Bernoulli(½−ε)`, `TV / √(I/2) → 1` as `ε → 0`. Hence the
> `√I` rate and the constant `√(1/2)` cannot be improved in the small-signal limit.

*Verified:* `test_information_bound_holds_random` checks the inequality **and** the
exact value `Δu·√(I/2)` against an independent recomputation (a loosened or
tightened constant is killed — confirmed by mutation);
`test_tv_bound_is_tight_for_indicator_utility` pins Prop 4.1;
`test_pinsker_constant_is_rate_optimal_in_the_small_signal_limit` drives ε→0 and
checks the ratio climbs to `>0.99` while staying `≤1`.

---

## 5. The budgeted identifiability window

Section 4 of `IDENTIFIABILITY_THEORY.md` observed empirically that a benchmark can
be non-identifiable at `λ=0` (quality dominance), identifiable at `λ≈1`, and
non-identifiable again at `λ=2` (over-penalised). This section proves the structure
behind that window. Define the **Lagrangian utility** `U_λ[c,a] := U[c,a] − λ·K[a]`
and let `V_oracle(λ)`, `V_fixed(λ)`, `G(λ)` be the functionals of `U_λ`.

> **Theorem 5.**
> (a) `V_oracle(λ)` and `V_fixed(λ)` are each **convex, piecewise-linear, and
> non-increasing** in `λ ≥ 0`; consequently `G(λ)` is piecewise-linear and the
> identifiable set `{λ : G(λ) > 0}` is a **finite union of intervals**.
> (b) *(cost saturation)* If the cheapest action `a₀` is unique with margin
> `δ := min_{a≠a₀}(K[a] − K[a₀]) > 0`, then for every
> `λ > λ★ := Δu / δ`, `a₀` is the pointwise argmax in every context, so (Theorem 2)
> `G(λ) = 0`. Hence the identifiable set is contained in the **bounded window**
> `[0, λ★]`.

*Proof.* (a) `max_a(U[c,a] − λK[a])` is a max of affine functions of `λ` with
non-positive slopes `−K[a] ≤ 0`, hence convex, piecewise-linear, non-increasing;
`V_oracle(λ)` is a `p`-average of such, `V_fixed(λ)` is one such, and both inherit
the three properties. A difference of piecewise-linear functions is piecewise-linear
with finitely many sign changes, so `{G>0}` is a finite union of intervals.
(b) For `λ > Δu/δ` and any `a ≠ a₀`, in every context `c`:
`U[c,a] − U[c,a₀] ≤ Δu < λδ ≤ λ(K[a]−K[a₀])`, i.e.
`U[c,a] − λK[a] < U[c,a₀] − λK[a₀]`. So `a₀` attains the per-context max
everywhere; by Theorem 2, `G(λ)=0`. ∎

**Reading.** Identifiability is a *constrained*, *bounded* property. Below the
window a quality-dominant mechanism ties the oracle (`G(0)` may be 0); above `λ★` a
cost-dominant cheap mechanism ties it. Adaptivity can only pay for `λ` inside a
finite window whose right endpoint is the explicit ratio `Δu/δ`. This is exactly
the §6 pre-check discipline: sweep `λ` on a pilot, and if the constrained argmax
never varies, do not spend cloud compute.

*Verified:* `saturation_lambda` returns `λ★` and probes `G` just above it (0
failures over 10⁴ problems, `test_cost_saturation_kills_the_gap_above_lambda_star`);
`test_budgeted_objectives_are_convex_and_nonincreasing` checks midpoint convexity
and monotonicity of both functionals; `identifiable_window` +
`test_binding_budget_creates_identifiability_positive_control` reproduce the
routing-v2 shape (unbudgeted gap ≈0, a strictly positive window under a budget).

---

## 6. The master inequality (fundamental theorem)

> **Theorem 6.** For any adaptive controller with router-visible signal `Z`,
> mechanism costs governing an operating budget `λ`, and route-decision cost
> `c_route ≥ 0`, the realised net value obeys
>
>   `V_net ≤ min{ G(λ),  Δu · √( I(C;Z) / 2 ) } − c_route.`
>
> Adaptive computation therefore pays (`V_net > 0`) only in the **intersection** of
> three admissible regions: the oracle gap must be positive (no dominance,
> Theorems 2 & 5), the signal must carry enough information (Theorem 4), and the
> decision must be cheaper than the value it unlocks.

*Proof.* `V_net = V(Z) − c_route`. By Theorem 3 (applied to `U_λ`, whose additive
per-action shift leaves the gap structure intact), `V(Z) ≤ G(λ)`; by Theorem 4,
`V(Z) ≤ Δu·√(I/2)`. Take the minimum and subtract `c_route`. ∎

**Three independent vetoes.** Each ceiling can vanish on its own: (i) a weakly
dominant mechanism sends `G(λ) → 0` (dominance veto); (ii) an uninformative signal
sends `I(C;Z) → 0` (information veto); (iii) a signal that is informative but
expensive to read sends `c_route → c_expensive` (computation veto). The CWC record
instantiates all three — routing v1/RCFR/plasticity (veto i, `G=0` unbudgeted),
surface-matched routing (veto iii, `c_route ≈ c_expensive`), and the general
requirement that difficulty be *cheaply predictable* (veto ii bounding what a cheap
probe can extract). A positive oracle gap is necessary but, by this theorem, far
from sufficient.

*Verified:* `signal_value` returns `master_bound = min(G, Δu√(I/2)) − c_route`;
`test_master_inequality_holds_random` checks `V_net ≤ master_bound` **and** the
exact value of `master_bound` and `V_net` against independent recomputation (a
`min→max` mutation is killed); the harness worst violation is ≈10⁻¹⁵.

---

## 7. Consequences for the CWC programme

1. **Every negative is a veto, not a refutation of adaptivity.** Theorems 2 and 5
   show the four `G=0` results are the weakly-dominant/over-penalised regimes, not
   evidence that adaptive mechanisms lack value — precisely the correction in
   `IDENTIFIABILITY_THEORY.md` §8, now with an exact `⇔` and a bounded window.
2. **Act J needs all three ceilings positive on a pilot.** Before cloud compute,
   estimate `G(λ)` (does the constrained argmax vary in `[0,λ★]`?), the
   cheap-probe information `I(C;Z)` (Theorem 4), and the cheap-vs-oracle probe gap
   (`c_route`). The decisive question is not "does difficulty vary?" but "does it
   vary, is it cheaply legible, and is reading it cheaper than the value it buys?"
3. **The theory is falsifiable and self-checking.** `make -f Makefile.cwc
   experiment-tests` runs the suite; `PYTHONPATH=. .venv/bin/python
   experiments/common/adaptive_value_theory.py` prints the adversarial report. Any
   future edit that weakens a bound is caught by the exactness assertions.

## 8. Epistemic status

These are **mathematical theorems** (proved, and numerically falsification-tested),
not empirical claims. They constrain the *value* any controller can realise on a
given `(U, π, K, c_route)`; they say nothing about whether a *specific* CWC
architecture attains a positive `V_net` on a real workload — that remains
`CWC-L7-pareto: NOT_TESTED`. The note is the mathematical scaffolding under the
existing identifiability and routability results, not a new rung on the claim
ladder.

## Relationship to sibling documents

* `docs/IDENTIFIABILITY_THEORY.md` — §1–2 oracle-gap decomposition (Theorem 1
  here), §4 constrained identifiability (Theorem 5 here), §9 route-decision cost
  (Theorem 6 here). This note supplies the `⇔` (Theorem 2) and the bounded window.
* `docs/ROUTABILITY_INFORMATION_BOUND.md` — the Pinsker bound (Theorem 4 here),
  now with tightness (Props 4.1–4.2) and its place in the master inequality.
* `experiments/common/value_information.py` — the original finite-case verifier for
  the information bound; `adaptive_value_theory.py` generalises it to all six
  theorems and adds the adversarial harness.
