# PREREGISTRATION — WP5-AC2 Learned Compute-Controller

**Committed before the run.** AC1 showed adaptive-compute allocation is *identifiable* (oracle
`K=d` beats fixed compute). This tests whether a **learned, reward-only controller** recovers that
allocation out-of-sample — the compute-axis analog of the L4a plasticity governor.

## Design (frozen)

- Reward `U_λ[d][K] = acc[d][K] − λ·K/3` from the committed AC1 raw runs
  (`artifacts/wp5-adaptive-compute-identifiability/raw_runs`, 8 seeds), operating `λ = 0.5`.
  Contexts = difficulty `d ∈ {1,2,3}`, actions = compute `K ∈ {1,2,3}`.
- **Controller:** per-difficulty softmax policy `π(K|d)`, REINFORCE with a moving-average baseline,
  learning from the reward of the sampled `K` on a randomly drawn TRAIN seed (never the oracle).
  Train seeds `{0,1,2,3}`, evaluate on held-out `{4,5,6,7}`. 8 controller inits; report the worst.
- Held-out recovery `= (learned − best_fixed)/(oracle − best_fixed)`.

## Controls (mandatory)

- **NULL falsifier:** collapsed reward (all difficulties get the `d=1` row) ⇒ no allocation value ⇒
  learned `null_recovery ≤ 0.10`.
- **Random baseline:** a uniform-`K` policy must trail `best_fixed`.

## Decision rule (FROZEN)

- **AC2_CONTROLLER_RECOVERS** iff worst-of-8 held-out recovery `≥ 0.8` AND `null_recovery ≤ 0.10`
  AND `random < best_fixed`. A reward-only controller learns adaptive compute-allocation.
- **AC2_NOT_RECOVERED** — worst recovery `< 0.8`.
- **AC2_VOID** — NULL or random control fails.

## Scope / prohibited

Tier `SYNTHETIC`. A learned compute-controller on the second mechanism, given-difficulty regime
(controller sees `d`). New claim `CWC-AC2-compute-controller`. Does NOT establish inferred-difficulty
routing, real-workload, L7 Pareto, or independent replication.
