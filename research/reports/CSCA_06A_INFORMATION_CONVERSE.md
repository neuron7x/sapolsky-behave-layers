# CSCA-06A — Information-Theoretic Compute Converse

**Status:** mathematical/post-confirmatory diagnostic; no experimental claim upgrade.

## Result

Let `T` be the binary event that an intervention experiment rejects a composite causal model class `P_M`. Suppose the test has uniform type-I error

`sup_{Q in P_M} Q(T=1) <= alpha`

and desired power under the true intervention law `P*`

`P*(T=1) >= 1-beta`.

For every `Q in P_M`, KL data processing through the measurable map from the full experiment to `T` gives

`KL(P* || Q) >= kl(P*(T=1) || Q(T=1)) >= kl(1-beta || alpha)`.

Therefore the **necessary** composite information condition is

`inf_{Q in P_M} KL(P* || Q) >= kl(1-beta || alpha)`.

For a fixed intervention design whose profiled separation rate is

`R_M = inf_Q KL(P* || Q) / Cost`, 

a necessary compute/intervention budget is

`Cost >= kl(1-beta || alpha) / R_M`.

This is a converse. Passing the bound means only that the requested operating point is not information-theoretically ruled out; it is not sufficient for finite-sample power.

## Frozen CSCA-06A operating point

At `alpha=0.01` and target power `0.95`:

`kl(0.95 || 0.01) = 4.176898950135489 nats`.

For the strong structural families S1/S2/S3, `R_M=0.22438095693074434 nat/cost`, hence

`Cost_necessary >= 18.61521141219082`.

The experiment allowed cost 256, so the desired power was not ruled out. R1 empirically rejected all 128/128 strong alternatives at median cost 64 in both fresh cohorts.

For weak-edge stress W1, `R_M=0.00985793158220849 nat/cost`, hence

`Cost_necessary >= 423.70946839131244`.

The frozen maximum cost 256 is **below a necessary information bound** for simultaneously achieving size 0.01 and power 0.95 against the closest member of the declared null class. Thus W1's near-total abstention is not evidence that the R1 decision rule merely needs tuning: under the controlled model assumptions, the requested operating point is impossible at that budget.

For the E0 equivalence control, `R_M=0`; the necessary cost is infinite. Repeating the same non-separating intervention cannot falsify the model class.

## Engineering consequence

Before allocating compute, the governor can evaluate:

`required_nats = kl(target_power || alpha)`

and

`necessary_cost = required_nats / R_M`.

If `max_cost < necessary_cost`, the correct state is

`BUDGET_BELOW_NECESSARY_INFORMATION_BOUND`,

not "run a larger model", "lower the threshold", or "collect more of the same data" within the already-fixed budget.

## Boundary

The certificate inherits the declared intervention law and nuisance class. If hidden confounding or other nuisance mechanisms lie outside `P_M`, this theorem does not permit topology-specific attribution. It controls the information required to falsify the **composite declared model class**, not metaphysical graph truth.
