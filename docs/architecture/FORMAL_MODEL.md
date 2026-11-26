# Formal model and proof obligations

This reference derives the propositions used to interpret the implementation at [`8617187`](https://github.com/neuron7x/sapolsky-behave-layers/commit/861718751198deeeda54a23efacb2227a819b49f). Frozen protocols govern domains, thresholds and admissible conclusions.

## Adaptive computation and information cost

Fix a common admissible action set and put benefits and costs in the same utility units. Let `U(c,a)` be utility before the incremental policy-specific routing cost. Define

```text
V_fixed  = max_a E[U(C,a)]
V_oracle = E[max_a U(C,a)]
G        = V_oracle − V_fixed
V_pi     = E[U(C,A_pi)]
Δ_net    = V_pi − V_fixed − c_pi
```

Pointwise, `U(C,A_pi) ≤ max_a U(C,a)`, including a randomized policy. Taking expectations gives `Δ_net ≤ G − c_pi`. Equality requires oracle utility almost surely under this model, with the same utility and cost definitions. `G ≥ 0` by comparing the maximum to the best fixed action. A positive `G` therefore supplies an opportunity. An actual policy must demonstrate its own gain and account for the cost of acquiring or computing its decision signal. Keep this utility formulation distinct from an empirical test with separately constrained resource counters. [Identifiability theory](../IDENTIFIABILITY_THEORY.md) · [baseline and compute parity policy](../evaluation/BASELINE_SELECTION_AND_COMPUTE_PARITY_POLICY.md).

WP4 checks the synthetic identity `adaptive − static = P_sample(m > K)` under a free exact halt oracle when `K = round(E_sample[m])`. The report evaluates measured compute parity separately. The learned adaptive-depth successor R2 failed its frozen acceptance criteria. [WP4 correction](../vnv/EPISTEMIC_CORRECTION_WP4_2026-07-19.md) · [programme decision](../vnv/CWC_PROGRAM_DECISION_2026-08-11.md).

## Finite decision sufficiency

For finite nonempty compatible worlds `W`, actions `A`, exact losses `L(w,a)` and tolerance `ε ≥ 0`, define `r(w,a)=L(w,a)−min_b L(w,b)`. An action is sufficient exactly when `max_{w∈W} r(w,a) ≤ ε`, equivalently when it belongs to the intersection of the worlds' acceptable-action sets. Expand the universal quantifier to obtain the equivalence. A unique minimax-regret action can still exceed the tolerance. Pairwise intersections can all be nonempty while the full intersection is empty. When it is empty, select one violating world for each action to obtain a witness of at most `|A|` worlds.

Under the protocol's finite deterministic test catalogue, exact outcomes intersect the world set and tests incur positive costs. The optimal worst-case acquisition cost minimizes the first test's cost plus the maximum continuation cost over its possible branches. Induction on remaining tests proves the recurrence. An exhausted search budget gives UNKNOWN. Impossibility requires proof within the specified catalogue. [Decision-sufficiency protocol](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cwc_decision_sufficiency/PROTOCOL.md#L7-L37).

## Exact certificates for the shared-sample relaxation

Let `F` be worlds compatible with H's synthetic measurement and reference contract. With positive gain `g`, offset `b`, drift `d`, intrinsic samples `I_k = B_k + sum_j A_kj x_j` and `x ≥ 0`, lift a world to `z=(x,b/g,d/g,1/g)`. Divide its necessary measurement and calibration strips by `g`. The outward coefficient bounds give rational rows `Az ≤ b_lp` shared across all seven times. Applying the same lift and outward inequalities to every world establishes `lift(F) ⊆ Q={z:Az≤b_lp}`. This direction depends on the declared H model and the validity of the outward coefficient bounds. The two row constructions share the input parser and coefficient implementation.

If a checker verifies `λ ≥ 0` and `Aᵀλ=q`, multiply each row by its multiplier and sum. Every `z∈Q` then satisfies `qᵀz ≤ b_lpᵀλ`. For `q=0` and `b_lpᵀλ<0`, a feasible `z` would imply `0<0`. This certifies exclusion under the model. A feasible outer point may be spurious. A valid upper bound can be nonoptimal. A missed certificate leaves the relevant obligation unresolved.

The exact Python checker binds the reconstructed system, target and multiplier roster, and recomputes the bound with rational arithmetic. The proposer may fail or exhaust its budget. A receipt separately records the proof and forces physical joint existence to false. A decision claim would need certified bounds against every relevant competitor and a separately checked existence witness. [Frozen protocol](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/PROTOCOL.md#L5-L35) · [dual check](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/kernel.py#L91-L125) · [shared row dependencies](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/kernel.py#L156-L247) · [receipt](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/kernel.py#L271-L295).

## External empirical obligation

`REAL-TRANSFER-01` treats AVeriTeC and HybridQA as two frozen workload families. Authenticate source and model/runtime bytes. Freeze policies and thresholds before held-out execution. For AVeriTeC, matching to the two direct comparators requires both forward calls and total tokens to be no larger. For HybridQA, the amendment defines resource comparisons and a necessary-query recall eligibility floor of 0.90 for direct comparators. When no direct comparator qualifies, the matched-compute claim remains `NOT_TESTED` even if behavioral evidence exists. A valid failed PRIMARY ends the flagship under the charter. A missing or invalid execution leaves the empirical verdict `NOT_TESTED`. [Preregistration](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/real_transfer_01/PREREGISTRATION.md#L140-L235) · [amendment 002](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/real_transfer_01/PRE_EXECUTION_AMENDMENT_002.md#L37-L80) · [stop rule](../../CWC_CLOSURE.md#2-final-state-and-stop-rule).

The linear-algebra argument, exact Python replay, and external measurement carry separate obligations. Mechanization in a theorem prover and nonlinear completeness remain deferred under the [closure charter](../../CWC_CLOSURE.md#4-authority-and-dependencies).
