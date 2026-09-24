# DGC Mathematical Hardening v2d — Runtime Statistical Authority, Drift, Shift, Geometry and Meta Bounds

Status: executable restricted-production mathematics. This document does **not** claim general adaptive validity, universal stationarity detection, general causal identification, or globally solved metareasoning.

## P21 — Anytime bounded conditional-mean change alarm

For bounded observations `X_t in [L,H]`, normalize `Z_t=(X_t-L)/(H-L)`. Under the upward-null conditional mean constraint

`E[Z_t | F_{t-1}] <= m0 + tau`,

and predictable `lambda_t >= 0`, Hoeffding's lemma yields the nonnegative supermartingale

`E_t^+ = prod_s exp(lambda_s (Z_s-(m0+tau)) - lambda_s^2/8)`.

Apply the same construction to `1-Z_t` for downward departures. Allocating `alpha/2` to each side gives an anytime-valid two-sided alarm threshold `2/alpha` by Ville + union bound. Dependence is allowed through the filtration under the conditional-mean null. Predictability of `lambda_t` is an external obligation. **No alarm is not a stationarity certificate.**

## P22 — Pre-outcome propensity trace certificate

The restricted adaptive-sampling theorem is now tied to execution provenance. Every sampled item records a policy digest, the selected propensity, a strictly increasing selection event index and a later outcome event index. Admission requires:

- a verified append-only telemetry chain;
- exact policy-digest match;
- positive target support;
- `pi_t(i) >= pi_min`;
- `q(i)/pi_t(i)` below the certified importance-weight cap;
- selection commitment strictly before outcome observation.

This blocks post-outcome propensity rewriting and hidden low-propensity sampling from inheriting adaptive-IPW authority.

## P23 — Target-mean LCB under bounded covariate shift

Let source samples be iid from `P`, `Y in [L,H]`, and let `w=dQ/dP` be a target/source density ratio bounded by `W`. For `Z=(Y-L)/(H-L)`, `wZ in [0,W]` and

`E_P[wZ] = E_Q[Z]`.

Hoeffding therefore yields a finite-sample lower confidence bound for the **target expectation**. When approximate weights are used, an externally certified mean-error budget `epsilon_w >= |E_P[(w_hat-w)Z]|` is subtracted.

This is not weighted conformal prediction and does not provide per-example coverage. It fails closed for unbounded ratios, target-support failure or post-hoc weight-error budgets.

## P24 — Audited continuous weighted-L1 Wasserstein geometry

Define

`c(x,y) = sum_i a_i |x_i-y_i|`, `a_i > 0`.

If external authority certifies

`|g(x)-g(y)| <= sum_i L_i |x_i-y_i|`,

then `g` is `K`-Lipschitz in this transport metric with

`K = max_i L_i/a_i`.

This makes the geometry feeding a Wasserstein penalty `K*rho` explicit and auditable. DGC does not infer feature semantics, scaling weights, coordinate Lipschitz constants or radius `rho` from this algebra alone.

## P25 — Transition-local metareasoning branch-and-bound

For a compute operation `c` with transition distribution over next meta-states, suppose caller provides for every next state `s'`:

- `D(s')`: stop/external-decision value;
- `U(s')`: an externally justified upper bound on the optimal future meta-value for every remaining horizon.

Then

`-cost(c)+E[D(S')] <= Q*(c) <= -cost(c)+E[U(S')]`.

This produces a root lower policy value, a global upper value and a certified suboptimality gap. If STOP exceeds all operation upper bounds, STOP is globally optimal. If one operation's lower bound exceeds STOP and every other operation's upper bound, that operation is globally optimal. This is tighter than a single root-level perfect-information ceiling whenever transition-local upper bounds are informative.

## P26 — Production strict-math admission

`ComputeGovernor.select(..., production_strict_math=True)` rejects a positive VOC unless an exact `StatisticalInferenceCertificate` is bound to the same estimate digest and includes non-empty sampling-policy, sampling-trace, calibration and drift-guard digests. A drift-invalidated certificate or an estimate swap after certification fails closed.

The certificate does not manufacture statistical validity; it binds runtime admission to separately established statistical authority.

## Verification

Local v2d evidence in the available integration workspace:

- `tests/test_dgc_math_v2d.py`: **14/14 PASS**;
- governance + v2d runtime tests: **26/26 PASS**;
- old DGC core/governance/finance + v2d regression: **37/37 PASS**;
- `scripts/dgc_math_v2d_attack.py`: **6/6 KILLED**;
- canonical `scripts/dgc_verification_gate.py` after v2d integration: **17/17 KILLED**;
- compileall for new governance modules: PASS.

These are local executable checks, not remote GitHub Actions authority.

## Remaining boundaries

Still open: arbitrary adaptive search with unknown propensities, target support failure, client-estimated density-ratio validation, adversarial/non-detectable drift, change-point localization guarantees, learned/high-dimensional geometry validation, general graphical causal identification, scalable metalevel MDP approximation theory, and independent formal review.
