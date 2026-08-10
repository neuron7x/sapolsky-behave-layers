# S01 minimal conceptual reproduction — Skill/Luck

Status: preregistered before execution in this repository revision.

Goal: independently reproduce one narrow qualitative property from S01: trajectory-specific counterfactual Shapley credit must assign zero credit to the terminal action on a realized Luck trajectory where that action cannot affect reward, while assigning positive credit to the corresponding action on a Skill trajectory.

This is **not** a reproduction of the paper's full estimator, PPO training, PTR, or benchmark suite.

## Environment
Two-step MDP-SCM:

- `X1=0` selects Skill; `X1=1` selects Luck.
- On Skill, terminal reward `Y=X2`.
- On Luck, terminal reward `Y=U`, where `U` is exogenous Bernoulli luck.
- Current policy and intervention baseline are both uniform over binary actions.

Counterfactual simulation follows the paper's declared qualitative rule: observed values are reused while parents remain on the observed trajectory; if an intervention changes the state, non-intervened downstream actions are resampled from the current policy; intervened actions are sampled from the baseline policy.

## Frozen test trajectories
- Skill: `X1=0, X2=1, U=1`, observed `Y=1`.
- Luck: `X1=1, X2=1, U=1`, observed `Y=1`.

## Primary predicates
1. `phi_skill_X2 > 0`.
2. `abs(phi_luck_X2) <= 1e-12`.
3. Naive return credit assigns equal positive credit to `X2` on both trajectories, exposing the confound.
4. Shapley efficiency holds numerically for both trajectories.

Failure of any predicate => `S01_SKILLLUCK_CONCEPT_NOT_REPRODUCED`.
