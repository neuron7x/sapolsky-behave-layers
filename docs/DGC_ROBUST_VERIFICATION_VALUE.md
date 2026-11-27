# Robust verification value

The same observable signal can have incompatible implications under two
plausible causal models. A policy must commit to one signal-to-action mapping
before the model is known. For a finite registered set of deterministic
policies, score each policy by its minimum expected net improvement over the
declared no-verification action. Authorize verification when the maximum of
these minima is strictly positive. This is a finite decision problem in the
sense of [Blackwell](https://doi.org/10.1214/aoms/1177729032), with an explicit
worst-case comparison over multiple models.

Inputs are integer incremental utilities, integer joint masses over latent
states and observable signals for each model, a fixed verification cost in the
same units, and precomputed admissible actions for each signal. Normalize each
joint mass array by its own positive total. Action zero is the fallback with
zero incremental utility in every state. Include its constant policy in the
candidate set. Resolve ties by lexicographic order and decline at zero.

## Falsification cases

Fix two equally likely states and a fallback whose utility is zero. Action one
yields +10 in state one and −10 in state zero. Charge one unit. With the state
revealed, intervene only in state one and obtain net +4. Add a model in which
the signal labels are reversed. Each model individually still offers +4, but
no common deterministic policy yields positive net value. The robust optimum
is −1. If only the fallback remains admissible, even the original perfect
signal yields −1. Charging five units instead makes the original informed
policy break even and verification is declined.

The certificate is conditional on the declared models, strategy set, utility
baseline and admissibility sets. The input author must establish coverage of
decision-relevant shifts, justify utilities as intervention consequences,
and account for all incremental costs. If the declared fallback is weak, a
positive value can reflect an available action change without information.
Use an independently established no-verification baseline before interpreting
the result as value caused by a signal. The evaluator is a research oracle.
It has no deployment authority and does not modify the live router.
