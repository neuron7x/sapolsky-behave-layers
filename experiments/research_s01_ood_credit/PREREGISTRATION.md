# S01 OOD causal-credit qualifier — preregistration

Status: preregistered before authoritative execution in git.

## Scope
Independent controlled qualification of the **causal-credit definition**, not a full reproduction of S01 training, estimator, PPO, PTR, or benchmark results.

## SCM
Four temporally ordered candidate events are observed before a delayed scalar outcome:

- `A` — true manipulable delayed cause at t1.
- `C` — correlated non-cause at t2; it is a readout of exogenous `U`, not a parent of `Y`.
- `D` — independent stochastic distractor at t3.
- `B` — temporally adjacent distractor at t4.

Structural outcome:

`Y = beta * A + gamma_context * U + epsilon`, with stable `beta=1`.

`C = U`. Intervening on the observed readout `C` does not modify exogenous `U`, hence `do(C)` has no causal effect on `Y`.

Contexts alter `gamma_context`, so observational leverage of `C` changes while the interventional effect of `A` is invariant.

## Frozen contexts
- `TRAIN_CONFOUNDED`: `gamma=2.0`
- `OOD_WEAK_CONFOUNDER`: `gamma=0.2`
- `OOD_SIGN_FLIP`: `gamma=-1.5`

## Frozen sampling
- 128 independent seeds (`1000..1127`).
- 256 independent trajectories per context/seed.
- `A,U,D,B ~ Bernoulli(0.5)` independently.
- `epsilon ~ Normal(0, 0.20)`.

## Credit methods
1. `EXACT_CF_SHAPLEY`: exact coalition enumeration over candidates `{A,C,D,B}` with Bernoulli(0.5) intervention baseline. Exogenous `U,epsilon` are held fixed. A candidate is scored by mean absolute trajectory credit.
2. `OBS_ASSOC`: absolute Pearson correlation with observed `Y`.
3. `RECENCY`: deterministic temporal-proximity score; later candidate = larger credit.
4. `EQUAL`: equal credit null.

## Primary predicates
On **each OOD context**:

1. `EXACT_CF_SHAPLEY` ranks `A` uniquely first on 128/128 seeds.
2. Mean false-credit mass (`C+D+B`) under `EXACT_CF_SHAPLEY` <= `1e-12`.
3. Shapley efficiency error <= `1e-12` on every checked trajectory.
4. `OBS_ASSOC` is not permitted to count as causal evidence even when it ranks a non-cause highly.

## Secondary diagnostics
- top-1 rate by method/context;
- normalized false-credit mass;
- score stability across context shifts;
- exact counterfactual evaluation count.

## Failure rule
Any failure of predicates 1–3 => `S01_OOD_CAUSAL_CREDIT_NOT_QUALIFIED`.

A PASS has **no architecture-promotion authority**. It only qualifies exact counterfactual Shapley as a synthetic target/teacher for subsequent matched-budget estimator tests against `resolution_aware_debt()`.
