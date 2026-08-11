# NPI-01 — Nullspace-Projected Inhibitory Control

Date frozen: 2026-08-12
Status: PREREGISTERED / NO RESULT OBSERVED

## Research question

Can structural non-identifiability be converted directly into a cheap inhibitory control signal without solving the full robust decision problem?

The proposed primitive projects local action-value sensitivity onto the observation-identifiability nullspace and inhibits action only when an observationally invisible parameter direction is first-order action-relevant.

## Formal object

Let latent causal parameters be `theta in R^p`, observations be `y = f(theta)`, and

`J(theta) = d f(theta) / d theta`.

Let `N(theta)` be an orthonormal basis for `ker J(theta)`, the locally observationally invisible directions.

For current best action `a*` and competitor `b`, define the action-value margin

`Delta_b(theta) = U(a*, theta) - U(b, theta)`

and first-order nullspace action sensitivity

`S_b(theta) = || N(theta)^T grad_theta Delta_b(theta) ||_2`.

The candidate inhibitory primitive authorizes execution when every current margin is positive and every `S_b = 0`; otherwise it inhibits and requests further intervention/evidence.

## Strong confirmatory hypothesis H-NPI-01

There exists a strictly positive safety-radius rule `R` determined only by the first-order local certificate

`C(theta0) = {f(theta0), J(theta0), N(theta0), Delta_b(theta0), grad Delta_b(theta0)}`

such that, whenever all current margins are positive and all nullspace sensitivity scores are zero, the current optimal action is invariant for every observationally equivalent `theta'` inside distance `R(C(theta0))`.

Operationally: a zero first-order nullspace score plus positive action margin is sufficient to certify a nonzero action-safe neighborhood without requiring curvature/set-valued robust analysis.

## H0 / kill condition

H-NPI-01 is NOT_SUPPORTED if there exists a smooth (C-infinity is sufficient) family of decision systems for which:

1. the observation map, Jacobian, nullspace, action margin, and action-value gradient at `theta0` are identical;
2. the NPI score is exactly zero and the current action margin is strictly positive;
3. for any proposed positive radius based only on that identical first-order certificate, a member of the family contains an observationally equivalent point inside that radius where the preferred action reverses.

A constructive analytic counterexample is sufficient. No learned-model experiment may rescue this strong hypothesis after the counterexample is verified.

## Frozen counterexample family

Use `theta=(u,v)`, observation `y(theta)=u`, so `J=[1,0]` and `ker J = span(e_v)`.

At `theta0=(0,0)`, define two actions with value difference

`Delta_K(u,v) = m - K v^2`, with frozen `m=1` and variable `K>0`.

At `theta0`, every family member has exactly:

- `y=0`
- `J=[1,0]`
- `N=e_v`
- `Delta_K=1`
- `grad Delta_K=(0,0)`
- `S=0`

For a proposed radius `r>0`, choose `K = 8/r^2` and evaluate at `theta'=(0,r/2)`.
Then `theta'` is observationally equivalent to `theta0`, lies strictly inside radius `r`, and

`Delta_K(theta') = 1 - (8/r^2)*(r^2/4) = -1`.

Thus the preferred action reverses despite an identical positive-margin zero-score first-order certificate.

## Frozen test radii

The executable falsifier must verify the construction independently at:

`r in {1, 1e-1, 1e-2, 1e-4, 1e-8}`.

For every radius, all certificate components at `theta0` must be byte/numerically identical within exact arithmetic where possible, the test point must satisfy `||theta'-theta0|| < r`, observation equality must hold exactly, and `Delta(theta') < 0`.

## Mutation attacks

The falsifier must reject at least these attacks:

1. observable `v` added to `y`;
2. nonzero first-order `v` gradient added to `Delta`;
3. test point moved outside the proposed radius;
4. `K` too small to reverse the action;
5. nonpositive baseline action margin;
6. nullspace basis not aligned with the invisible direction.

## Decision rule

- All frozen radii satisfy the counterexample and all six mutations are killed => `NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED`.
- Any construction invariant failure => `HARNESS_INVALID`, not support for H-NPI-01.

## Claim boundary

A negative verdict kills only the *first-order sufficiency* claim. It does not imply that identifiability-aware inhibition is impossible.

A curvature-bounded or set-valued robust certificate may still be valid. In particular, any successor must explicitly control higher-order variation (for example a Hessian/Lipschitz bound) or directly optimize worst-case action over the observational equivalence set.

## Related-work / novelty boundary frozen before execution

The adjacent literatures include structural identifiability via sensitivity/nullspace analysis, rational metareasoning/value of computation, active information acquisition, abstention, and neural inhibitory control. The candidate combination tested here is narrower: using the structural-identifiability nullspace as an executable inhibitory gate on *action-relevant internal directions*.

No claim of global novelty is authorized. A pre-execution search on 2026-08-12 found adjacent work in each component but no exact first-order nullspace-to-action-inhibition certificate matching this formulation. Novelty status remains `PROVISIONAL / NOT EXHAUSTIVELY PROVEN`.
