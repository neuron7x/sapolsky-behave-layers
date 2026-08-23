# DGC Mathematical Hardening v2

Status: **normative mathematical engineering; no production or superiority claim**.

This document extends `DGC_MATHEMATICAL_CONTRACT.md`. The goal is not to add notation; it is to close failure modes in which a positive model-conditional VOC is mistaken for a robustly positive real decision value.

## P6 — total-variation robust VOC lower bound

Let a regret-like gross value `G` lie in `[L,H]`. Let `P` be the nominal world distribution and let the true distribution `Q` satisfy

\[
TV(P,Q) \le \varepsilon,
\qquad TV(P,Q)=\sup_A |P(A)-Q(A)|.
\]

For any bounded `G`,

\[
|E_QG-E_PG|\le \varepsilon(H-L).
\]

If a statistically valid nominal lower bound on `E_P G` is `g_L`, nominal compute cost is `c`, actual cost can exceed it by at most `\kappa`, and the utility function is uniformly misspecified by at most `\eta`, then for regret

\[
R_U(w;a_0)=\max_a U(w,a)-U(w,a_0)
\]

we have

\[
|R_U-R_{\tilde U}|\le 2\eta.
\]

Therefore a robust net lower bound is

\[
\boxed{VOC_L^{rob}=g_L-c-\varepsilon(H-L)-2\eta-\kappa.}
\]

A nominally positive VOC is insufficient whenever this robust bound is non-positive.

Implementation: `cwc/governance/robust_voc.py`.

## P7 — Wasserstein-Lipschitz robust VOC

If the world space has metric `d`, the gross value `g(w)` is `K`-Lipschitz, and the true world distribution lies in a 1-Wasserstein ball

\[
W_1(P,Q)\le \rho,
\]

then Kantorovich-Rubinstein duality yields

\[
E_Q g \ge E_P g-K\rho.
\]

Thus

\[
\boxed{VOC_L^{W_1}=g_L-c-K\rho-2\eta-\kappa.}
\]

This contract is valid only if the metric and Lipschitz constant have independent authority; declaring a small `K` post hoc is claim gaming.

## P8 — exact finite credal expectation

When scenario weights are not calibrated point probabilities, DGC may use interval probabilities

\[
l_i\le p_i\le u_i,\quad \sum_i p_i=1.
\]

For finite values `v_i`, minimizing or maximizing

\[
\sum_i p_i v_i
\]

over this credal set is a linear program. Starting from `p_i=l_i`, the exact minimum is obtained by assigning remaining probability mass to the smallest `v_i` up to their upper bounds; the maximum assigns it to the largest values. An exchange argument proves optimality.

This gives an exact expectation interval without inventing a midpoint prior.

Implementation: `cwc/governance/ambiguity.py::credal_expectation_interval`.

## P9 — robust perfect-information STOP certificate

For a **pure-information** operation that cannot change the world, legal actions, or utility, perfect revelation of `W` is at least as informative as the operation. With current action `a_0`, perfect revelation gains exactly

\[
R(W;a_0)=\max_a U(W,a)-U(W,a_0).
\]

Hence for every probability model `P`,

\[
VOI(c;P)\le EVPI(P)=E_P[R(W;a_0)].
\]

For a credal set `\mathcal P`, if

\[
\boxed{\sup_{P\in\mathcal P}EVPI(P)\le c_{min},}
\]

where `c_min` is a lower bound on the operation's actual cost, then every less-informative pure-information computation has non-positive VOC for every `P in mathcal P`.

This is a stronger STOP certificate than “estimated VOC is small.” It fails if the computation intervenes on the world or changes the available action set.

## P10 — minimax-regret action under probability ambiguity

When no probability semantics are justified, DGC may select a robust external action by

\[
a^{MMR}\in\arg\min_a\max_w\left[\max_b U(w,b)-U(w,a)\right].
\]

The implementation deterministically breaks ties lexicographically. This is not equivalent to expected utility and must not be mixed with probability-weighted claims.

## P11 — robust action stability and certified decision-irrelevant compute

For current action `a`, define its world-wise action margin

\[
m(w,a)=U(w,a)-\max_{b\ne a}U(w,b).
\]

Let

\[
m_{min}=\min_w m(w,a).
\]

If `|U_true-U_model|_infty <= eta`, each pairwise margin can shrink by at most `2 eta`. Therefore

\[
\boxed{m_{min}-2\eta>0}
\]

certifies that `a` remains strictly optimal in every admitted world and every utility model inside the declared ambiguity ball.

If a remaining compute suffix can only reveal which admitted world holds and cannot intervene on `W`, `A`, or `U`, that suffix has zero immediate action-switch value. Its cost is therefore **certified decision-irrelevant compute**.

For baseline total cost `C` and such a suffix cost `C_s`,

\[
\boxed{DICF_{cert}=C_s/C.}
\]

This is a lower bound on safely removable compute under the stated causal contract, not an upper bound on all possible optimization.

Implementation: `cwc/governance/decision_stability.py`.

## P12 — anytime-valid adaptive importance-weighted e-process

The original DGC sequential contract rejected all adaptive sampling. v2 supports a deliberately narrower valid case.

At time `t`, an adaptive sampler chooses item/stratum `I_t` with predictable probability `pi_t(i)>0`. Let fixed target mass be `q(i)`, outcome `X_t in [L,H]`, and

\[
Y_t=(X_t-L)/(H-L),\qquad
Z_t=\frac{q(I_t)}{\pi_t(I_t)}Y_t.
\]

Assume the propensity is fixed before observing `X_t`, importance weights are bounded by `w_max`, and `Z_t` is conditionally unbiased for one fixed target normalized mean `mu`. For any predictable `lambda_t >= 0`, Hoeffding's lemma gives under `H0: mu <= m`

\[
E_t(m)=\prod_{s\le t}
\exp\left(
\lambda_s(Z_s-m)-\frac{\lambda_s^2w_{max}^2}{8}
\right)
\]

as a non-negative supermartingale. Ville's inequality implies

\[
P\left(\sup_t E_t(m)\ge 1/\alpha\right)\le\alpha.
\]

Inverting the test yields an anytime-valid one-sided lower confidence bound. This **does not** validate arbitrary adaptive countermodel search: unknown propensities, support collapse, changing target distributions, or outcome-dependent selection violate the contract.

Implementation: `cwc/governance/adaptive_eprocess.py`.

## P13 — split-conformal gross-value lower prediction bound

For a frozen predictor `f(X)` and exchangeable calibration/test residuals

\[
R_i=Y_i-f(X_i),
\]

let `k=floor(alpha(n+1))` and `R_(k)` be the k-th smallest calibration residual. For `k>=1`,

\[
P(R_{test}<R_{(k)})\le \frac{k}{n+1}\le\alpha.
\]

Therefore

\[
Y_{test}\ge f(X_{test})+R_{(k)}
\]

with marginal probability at least `1-alpha`. If `k=0`, v2 returns `-infinity`; it refuses to manufacture finite certainty from insufficient calibration data.

Implementation: `cwc/governance/calibration.py`.

## P14 — conformal expected-risk control for monotone admission thresholds

For exchangeable bounded loss functions `L_i(lambda) in [0,B]` that are non-increasing as the safety threshold `lambda` becomes more conservative, choose the first threshold satisfying

\[
\frac{\sum_{i=1}^{n}L_i(\lambda)+B}{n+1}\le\alpha.
\]

Under the conformal-risk-control theorem, the expected next-sample loss at the selected threshold is at most `alpha`, subject to the exchangeability and monotonicity assumptions.

DGC uses this only as a calibration/risk-control primitive; it is not conditional-risk, adversarial-shift, or client-production evidence.

Implementation: `cwc/governance/risk_control.py`.

## P15 — simultaneous cost-quality Pareto certificate

For paired task differences

\[
D_C=C_{baseline}-C_{DGC},\qquad
D_Q=Q_{DGC}-Q_{baseline},
\]

DGC may claim a statistically certified Pareto improvement only when simultaneous confidence statements establish

\[
E[D_C]>0
\]

and

\[
E[D_Q]\ge -\epsilon_Q,
\]

where `epsilon_Q` is a preregistered non-inferiority margin (zero by default). v2 uses fixed-n bounded Hoeffding intervals with Bonferroni allocation across the two paired metrics. Dependence between cost and quality within each task is allowed; the union bound does not require metric independence.

A cost saving with a quality regression is therefore mathematically incapable of becoming `PARETO_PASS`.

Implementation: `cwc/governance/pareto.py`.

## Remaining mathematical blockers

v2 deliberately does **not** claim closure of:

1. arbitrary adaptive countermodel selection with unknown/learned propensities;
2. nonstationary target means without an independently bounded drift process;
3. hidden-state misspecification outside the declared TV/Wasserstein/credal sets;
4. strategic or endogenous utility functions;
5. general causal identifiability from text-only countermodels;
6. client-distribution calibration under unknown covariate/concept shift;
7. high-dimensional continuous-world ambiguity without validated geometry;
8. asymptotically efficient adaptive estimators (current e-process is conservative);
9. theorem-level external peer review of DGC-specific compositions;
10. novelty of the composition relative to metareasoning, routing, information design, sequential testing, robust decision theory and selective inference.

These blockers are why the mathematical maturity score remains near 80%, not 95%.

## P16 — finite-horizon meta-Bellman equation and myopic limitation

Let `D(s)` be the value of stopping metareasoning in state `s` and taking the best currently available external action. For compute operation `c` with cost `k_c` and transition law over successor metacognitive states,

\[
V_0(s)=D(s),
\]

\[
\boxed{V_h(s)=\max\left(D(s),\max_c\{-k_c+E[V_{h-1}(S')\mid s,c]\}\right).}
\]

The current runtime's one-step VOC corresponds to the `h=1` approximation. It is **not** generally equivalent to `V_h` for `h>1` because computations can be complementary. A concrete executable counterexample in `tests/test_dgc_mathematics_v2.py` has a first computation with negative standalone VOC but a two-step optimal value of `0.8`.

Therefore the implication

\[
\forall c:\ VOC_{1step}(c)\le0 \Rightarrow STOP_{global}
\]

is false in general.

A robust perfect-information STOP certificate from P9 remains valid for any finite adaptive **pure-information sequence**: the entire sequence cannot create more gross decision value than perfect revelation, while any non-empty sequence pays at least its first compute cost.

Implementation/oracle: `cwc/governance/metareasoning.py`.
