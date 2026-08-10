# S03 controlled latent-dynamics qualifier — preregistration

Status: preregistered before authoritative execution in git.

## Scope
Independent CWC mechanism qualification motivated by S03. This is **not** a reproduction of NeuroWorld, its fMRI benchmarks, architecture, or reported metrics.

Question: under partial observability, does a history-bearing transition model produce more stable causal rollouts than a capacity-matched stateless predictor when both receive only stimulus information admissible at each simulated step?

## Environment
Linear stochastic second-order system with hidden velocity:

- latent `z_t=(position_t, velocity_t)`;
- observation `x_t = position_t + observation_noise`;
- stimulus/action `a_t`;
- transition:
  - `position_{t+1}=position_t+velocity_t+0.5*a_t`;
  - `velocity_{t+1}=rho*velocity_t+a_t+process_noise`.

The current observation does not reveal hidden velocity; recent history can.

## Models — matched 4 input features
- `STATELESS`: `[x_t, a_t, x_t*a_t, a_t^2]`.
- `DYNAMIC_HISTORY`: `[x_t, x_{t-1}, a_t, a_{t-1}]`.
- `LEAKAGE_ORACLE`: `[x_t, x_{t-1}, a_t, x_{t+1}]` as an intentionally inadmissible positive leakage control.

All use the same closed-form ridge estimator and intercept. The leakage model is diagnostic only.

## Frozen execution
- 64 seeds: `2000..2063`.
- training: 1200 transitions/seed, `rho=0.85`, action scale `1.0`.
- ID test: 600 transitions, `rho=0.85`, action scale `1.0`.
- OOD test: 600 transitions, `rho=0.65`, action scale `1.35`.
- fixed process SD `0.08`, observation SD `0.05`.
- ridge alpha `1e-3`.
- rollout horizons `{1,2,4,8}`.
- during admissible rollout, only the stimulus `a_j` for the current transition is revealed at step `j`; future observations are never supplied.

## Primary predicates
On OOD test:
1. `DYNAMIC_HISTORY` has lower rollout MSE than `STATELESS` for >=56/64 seeds at horizon 8.
2. For every horizon, an exact two-sided sign test for paired per-seed MSE differences remains significant after Bonferroni correction across four horizons at family alpha 0.01.
3. `LEAKAGE_ORACLE` one-step MSE is below both admissible models, verifying leakage sensitivity.
4. No future observation enters `DYNAMIC_HISTORY` or `STATELESS` features.

Failure of any predicate => `S03_CONTROLLED_LATENT_DYNAMICS_NOT_QUALIFIED`.

## Boundary
PASS only qualifies a controlled transition-state mechanism. It has no neuroscience, NeuroWorld-reproduction, CWC-runtime, or architecture-promotion authority.
