# A Theory of Adaptive-Mechanism Identifiability

Status: research note, verified numerically by `scripts/identifiability_theory.py`
against the four CWC experiments (routing v1/v2, RCFR, plasticity).
Motivation: three preregistered oracle-gap gates collapsed to ~0 (routing v1,
RCFR, plasticity) while one succeeded (routing v2). This note derives the exact
condition that separates them, and turns it into a cheap pre-check before any
cloud-scale Pareto run (Act J).

## 1. Object

An adaptive controller chooses, per **context** `c ∈ C`, a **mechanism**
`a ∈ A` (a route, a parameter group, an expert, an adapter). Let `U[c,a]` be the
utility (quality, or quality minus a resource penalty). Contexts occur with
weights `p_c`. Define

- oracle value  `V_oracle = Σ_c p_c · max_a U[c,a]`  (choose per context),
- best-fixed value `V_fixed = max_a Σ_c p_c · U[c,a]`  (one choice for all),
- **oracle gap** `G = V_oracle − V_fixed ≥ 0`.

`G` is exactly the *value of adaptivity*: how much a context-aware controller can
beat the best context-blind policy. A benchmark is **identifiable** iff `G > 0`
with statistical support — otherwise a learned controller cannot beat a constant
and must not be trained (the CWC gate discipline).

## 2. Exact decomposition theorem

Write the two-way ANOVA of `U` (weights `p` over contexts, uniform over choices):
`U[c,a] = μ + α_c + β_a + γ[c,a]`, with `α` the context main effect, `β` the
choice main effect, `γ` the **interaction** (`Σ_a γ[c,a]=0`, `Σ_c p_c γ[c,a]=0`).

Because `Σ_c p_c γ[c,a] = 0`, we get `V_fixed = μ + max_a β_a`, and

> **Theorem.** `G = 𝔼_c[ max_a ( β_a + γ[c,a] ) ] − max_a β_a`.

Proof: `V_oracle = μ + 𝔼_c α_c + 𝔼_c[max_a(β_a+γ[c,a])] = μ + 𝔼_c[max_a(β_a+γ[c,a])]`
since `𝔼_c α_c = 0`; subtract `V_fixed = μ + max_a β_a`. ∎
(Verified: the formula reproduces `G` to machine precision on all datasets.)

**Corollary 1 (interaction drives everything).** If `γ ≡ 0` then `G = 0`.
The value of adaptivity is *entirely* the context×choice interaction; main
effects `β` never create a gap.

**Corollary 2 (weak dominance kills the gap).** If some `a*` is *weakly optimal
in every context* — `β_{a*}+γ[c,a*] ≥ β_a+γ[c,a] ∀c,a` — then `G = 0`, no matter
how large `γ` is. A single always-best mechanism makes adaptivity worthless.

## 3. The two collapse regimes (what actually happened)

| Experiment | `G` | Why | Regime |
|---|---:|---|---|
| routing v2 (quality only) | 0.000 | semantic path solves EASY *and* HARD → weakly dominant | **quality dominance** |
| RCFR | 0.000 | DISeL-with-role matches RCFR everywhere → weak dominance | quality dominance |
| plasticity (λ=0) | 0.0001 | attention has the largest `β` and is never overtaken (`γ_RMS/β_spread = 0.41`) | **main-effect dominance** |
| routing v1/v1.1 | ≈0 | any block solved every subtask | quality dominance |

Every collapse is a **weakly-dominant mechanism** (Corollary 2): the most
expressive / most capable choice is ≥ all others across contexts, so a constant
policy ties the oracle. This is generic at small scale — expressive mechanisms
subsume weaker ones through the residual stream.

## 4. The central correction: identifiability is a CONSTRAINED property

Quality alone almost always has a dominant choice (the biggest mechanism wins).
Adaptivity acquires value only when a **cost** forbids using the dominant choice
everywhere. Give each mechanism a cost `K[a]`; impose a budget (a fraction `κ`
of contexts may use an expensive mechanism, or penalize with a Lagrangian `λ`):

> **Identifiability condition.** `G > 0` iff, at the operating budget, no
> mechanism weakly dominates the cost-adjusted utility — equivalently, iff
> `argmax_a ( Q[c,a] − λ·K[a] )` **varies with `c`** at the `λ` implied by the
> budget.

Routing v2 confirms this exactly. On quality the gap is 0 (semantic dominates);
under a 50% compute budget (`scripts/identifiability_theory.py`):

```
V_oracle = 1.000   (HARD→semantic, EASY→direct)
V_fixed  = 0.751   (best context-blind κ-allocation)
G        = 0.249   ← identifiable; this is the source of the empirical 99.8% CE gap
```

**The budget, not the quality difference, is what made routing identifiable.**

## 5. The theory self-corrects the plasticity verdict

The plasticity oracle-gap test measured `G` at `λ=0` (each group evaluated
independently, no cost in the oracle objective) → 0.0001 → `NOT_IDENTIFIABLE`.
But a budgeted controller is the entire premise of the AMG (cost §7.9). Adding
the real parameter cost `K` (head 512, attn 4096, mlp 8192 params) and sweeping
`λ`:

| `λ` (cost weight) | `G` | oracle allocation |
|---:|---:|---|
| 0.0 | 0.000 | (attention ties everywhere) |
| 0.5 | 0.109 | lexical→**head** (cheap, sufficient), relational→**attn** |
| 1.0 | **0.191** | lexical→head, relational→attn |
| 2.0 | 0.000 | over-penalized → head dominates |

At `λ∈[0.5,1.0]` the cost-aware oracle spends the **cheap** `head` group on
lexical (which head can solve) and reserves the **expensive** `attn` only for
relational (structurally necessary), beating every fixed group. The gap peaks at
`G ≈ 0.19`, **identical across all 5 seeds** (min 0.190, variance ≈ 0).

> **Result.** The plasticity benchmark *is* identifiable once update cost enters
> the oracle objective — which is exactly what a *budgeted* metaplasticity
> governor is for. The earlier `NOT_IDENTIFIABLE` was an artifact of an
> unbudgeted oracle test.

**Epistemic status: EXPLORATORY.** `λ` was chosen after seeing the data. This
generates a *preregisterable* hypothesis — "under a parameter-cost objective
with `λ≈1`, a governor that picks the cheapest-sufficient plasticity locus per
task beats any fixed locus" — which must be confirmed by a fresh run with a
cost-aware oracle and `λ` frozen before execution. The robustness (zero seed
variance) makes it a strong candidate, not a confirmed claim.

## 6. A cheap identifiability predictor (before spending cloud compute)

For any adaptive mechanism (routing, experts, plasticity, memory), before an
expensive confirmatory or cloud-scale run:

1. On a small pilot, estimate the utility matrix `Q[c,a]` and cost `K[a]` over a
   handful of contexts and mechanisms.
2. Pick the operating budget `λ` (or `κ`) from the intended deployment.
3. Compute `argmax_a(Q[c,a] − λK[a])` per context. If it is **constant** across
   contexts → **not identifiable at this budget** → do not train a controller,
   do not spend cloud compute. Redesign until the constrained argmax varies.
4. If it varies, estimate the constrained gap `G` and its seed CI; proceed only
   if the lower CI > 0.

This is O(|C|·|A|) arithmetic on a pilot — the identifiability of Act J can be
predicted for a few dollars of pilot compute instead of discovered after a full
cloud run.

## 7. Design principle for identifiable benchmarks

To make any adaptive mechanism identifiable, engineer **anti-dominance under
budget**: the mechanisms must be *Pareto-incomparable across contexts at the
operating cost* — each mechanism the constrained optimum for some context and
suboptimal for others. Concretely: a **competence–cost spread** where cheap
mechanisms suffice for easy contexts and expensive mechanisms are *necessary*
(not merely better) for hard ones. The positive control `U=[[1,0],[0,1]]` (each
choice best in exactly one context) gives the maximal gap `G=0.5`.

The two failure modes to avoid: (a) one mechanism strong enough to win every
context on quality (kill it with a binding budget); (b) a cost so high one cheap
mechanism wins everything (`λ=2` above — over-penalized).

## 8. Consequences for CWC direction

1. The three "failed" negatives were not evidence that adaptive mechanisms are
   worthless — they were evidence that **unbudgeted** small-scale benchmarks are
   non-identifiable by construction (Corollary 2). The routing-v2 success and the
   plasticity revival both come from a binding cost.
2. Act J (compute-equivalent Pareto vs MoD/MoE) is exactly a *budgeted* test, so
   it is the right frame — but run the §6 predictor on a pilot first: confirm the
   constrained argmax varies before committing cloud compute.
3. The plasticity direction is worth a fresh, cost-aware, preregistered oracle
   run — the math says the value is there once cost is in the objective.

## 9. Route-decision cost — a necessary discount on the oracle gap

Sections 1–8 treat the oracle gap `G` as the value of adaptive control. That is an
*upper bound*: it assumes the controller can identify the right choice for free. A
learned controller must actually *compute* which mechanism a context needs, at some
cost `c_route`. The realized value is therefore

```
V_realized = G − c_route.
```

Two empirical anchors (`artifacts/wp2-routing-v3-*`, 8 seeds each) pin the extremes:

- **`c_route ≈ 0` (surface-leaky benchmark).** On the S-R-O task, difficulty
  correlates with cheap surface features (length, histogram; leakage_probe AUROC=1.0).
  A REINFORCE controller with objective `L = L_task + λ·C_use` recovers oracle-level
  routing (AUROC 1.0, learned loss 0.009 vs random 0.48) — but **only at λ ≥ 1**
  (a binding budget), confirming §6: at λ ≤ 0.5 the quality-dominant mechanism wins
  everywhere and the route inverts. Crucially, this also shows the earlier
  straight-through *collapse* was an **optimization artifact**, not an absence of
  signal — the identifiability was real, the estimator was too weak.

- **`c_route ≈ c_expensive` (surface-matched benchmark).** When EASY/HARD are matched
  in length, first token, and token histogram, and differ only in a structural
  property (distance between the two occurrences of a duplicated value), no controller
  — neither a cheap mean-pool MLP nor an O(L²) self-attention controller — routes
  above chance (AUROC ~0.51, no loss saving), **even trained by direct supervision on
  the route label**. The difficulty signal is not cheaply computable: deciding the
  route requires ~the same search the expensive mechanism performs, so `V_realized ≈ 0`
  despite a large `G`.

**Consequence.** A positive oracle gap (§1–8) is necessary but not sufficient for a
usable adaptive architecture. Before any compute-equivalent Pareto claim (Act J), the
gap must be discounted by the *learned* route-decision cost on the target workload.
The decisive question for real workloads is not merely "does difficulty vary?" but
"is difficulty **cheaply predictable** from the input?" — an empirical property to
measure with a cheap-probe-vs-oracle-probe gap before spending cloud compute.
