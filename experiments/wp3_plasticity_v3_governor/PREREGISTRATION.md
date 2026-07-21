# PREREGISTRATION — L4a Learned-Governor study

**Committed before the run.** Tests the one thing L4 explicitly does NOT claim: that a
**learned** governor (not the exact oracle) recovers the confirmed cost-budget gap —
from **reward only**, and **out-of-sample**.

## Question

L4 (`SUPPORTED_NARROWED`) confirmed the *oracle* allocation beats every fixed allocation
under the λ=1 cost budget (`G_lo=0.111`, 16/16 held-out seeds). Its prohibited
extrapolation is "a learned governor achieves the gap." This experiment tests exactly
that: does a controller `π(group | context)` trained by policy gradient on **sampled
rewards** (never shown the oracle) recover the gap on **held-out seeds**?

## Design (frozen)

- **Rewards (real):** the measured cost-budget utility `U_λ=1[seed, task, group] =
  new_acc − cost/params_max` from `artifacts/wp3-plasticity-v2-confirmatory/raw_runs`
  (16 seeds). Contexts C = {lexical, relational}; arms A = {attn, mlp, head, embed}.
  Measured means: lexical → head 0.938 (next embed 0.68); relational → attn 0.500
  (next head 0.12). Margins are **wide** and reward noise small — a competent governor
  is EXPECTED to succeed; the informative content is reward-only credit assignment,
  out-of-sample generalization, and the NULL falsifier below.
- **Split:** train on seeds 5–12 (8), evaluate on **held-out** seeds 13–20 (8).
- **Governor:** per-context softmax policy, REINFORCE with a moving-average baseline,
  learning ONLY from the reward of the sampled arm on a randomly drawn train seed (the
  oracle label is never provided). Deterministic PRNG. Trained over
  `CONTROLLER_SEEDS = 8` independent initializations; report the **worst**.
- **Evaluation (held-out):** greedy policy `argmax_a π(a|c)`; realised utility =
  mean over contexts of the mean measured `U_λ=1` on held-out seeds for the chosen arm.
- **Baselines (held-out, honest):** `random` (uniform arm); `best_fixed` (the single arm
  maximizing train utility across both contexts, evaluated on held-out); `oracle`
  (per-context best on held-out) — the ceiling.
- **Recovery:** `(learned − best_fixed) / (oracle − best_fixed)`.

## NULL falsifier (mandatory — the instrument must be able to report "no gap")

Re-run the whole pipeline on a **collapsed** benchmark where both contexts are given the
SAME reward row (the lexical row). There the oracle = best-fixed, so no context-
conditioned policy can help. A trustworthy governor+metric must return
`null_recovery ≈ 0` (no manufactured gap). If it reports a positive recovery on the
null, the instrument is broken and the verdict is VOID.

## Decision rule (FROZEN)

- **L4A_SUPPORTED** iff, on held-out, over all 8 controller seeds:
  (1) `learned > best_fixed` for the **worst** controller seed;
  (2) worst-seed `recovery ≥ 0.80`;
  (3) `random < best_fixed` (sanity);
  (4) NULL falsifier: `null_recovery ≤ 0.10`.
- **L4A_NOT_SUPPORTED** — (1) or (2) fails (governor cannot recover the gap from reward).
- **L4A_VOID** — (3) or (4) fails (instrument untrustworthy).

## Scope / prohibited

Tier `SYNTHETIC`, **given-context** regime (task identity observed; `c_route=0`), wide
margins. A positive result shows a reward-trained governor realises the L4 oracle gap out
of sample **here** — it does NOT establish: surface-independent / inferred-context
routing, compute-equivalent Pareto (L7), energy/latency, real-workload generalization, or
independent replication. On success, L4's scope loses "no learned governor"; the claim
stays `SUPPORTED_NARROWED` and never becomes an L7 claim.
