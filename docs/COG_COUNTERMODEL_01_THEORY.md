# COG-COUNTERMODEL-01 — Countermodel Search Theory

## Structural reparameterization identity

Let the observable reduced form be

`X = a_x + lambda'R + eps_x`,

`Y = a_y + delta'R + eps_y`.

For every scalar `b`, define

`eta_b = delta - b lambda`,

`U_x = eps_x`,

`U_y = eps_y - b eps_x`.

Then exactly

`Y = b X + (a_y - b a_x) + eta_b'R + U_y`.

Thus the same factual process admits a continuum of structural decompositions with different causal coefficient `b`. In a Gaussian reduced-form model, the transformed latent residual covariance is

`Var(U_x)=sigma_xx`,

`Cov(U_x,U_y)=sigma_xy-b sigma_xx`,

`Var(U_y)=sigma_yy-2b sigma_xy+b^2 sigma_xx >= 0`.

The observed mean and covariance are unchanged. Therefore the observational KL divergence between these decompositions is exactly zero: their difference is structural semantics, not factual fit.

## What can identify b

Restrictions such as `eta_b=0` (exclusion), bounds on latent confounding, known assignment mechanisms, or intervention data can shrink the equivalence class. But these restrictions must retain their epistemic type. A countermodel being outside a declared bound means only *conditional identification under that bound*.

## Why a Pareto set is used

There is no invariant scalar notion of the "cheapest wrong world" without declaring a cost model. CWC therefore preserves a Pareto frontier over at least:

1. direct-effect debt `||eta_b||_2`;
2. latent-confounding debt `|Corr(U_x,U_y)|`;
3. causal displacement `|b-beta_ref|`.

A later governor may scalarize these only under an explicit preregistered decision cost. The countermodel generator itself must not invent a preference and then mistake it for evidence.

## Runtime rule

`countermodel survives -> causal consolidation blocked`

`no countermodel inside declared bounds + countermodels outside -> assumption-conditional identification only`

`invalid upstream epistemic state -> generator cannot upgrade it`

No result in this module can emit unconditional causal authority.
