# WP-4 Adaptive Compute Allocation — PREREGISTRATION

Registered 2026-07-16. The prediction under test was DERIVED in
`docs/IDENTIFIABILITY_THEORY.md` (committed 6322bed) BEFORE this experiment, so
it is a genuine prior prediction, not a fit.

## The frontier claim
The first narrow causal mechanism whose advantage cannot be explained by static
architecture, additional capacity, or optimization: **adaptive allocation of a
fixed compute budget across inputs of heterogeneous required depth.**

## Prediction (fixed by theory, before the run)
On a task where each input needs m(x) hops (measurable), a shared exact hop
operator, and an average compute budget K:
> adaptive − best-static solved-gap = **P(m > K)**, computed from the difficulty
> distribution P(m), for every distribution and seed.

## Design — allocation is the ONLY free variable
Exact hop operator (successor lookup) = the identical capable primitive for
every policy → per-hop compute and capacity matched by construction; no learning.
Task: pointer-chase to an absorbing fixed point; m(x)=hops; monotone;
non-lookup (random graph per example). Policies:
- static_K: K hops for all (best fixed).
- random_avgK: variable depth, mean K, INPUT-BLIND (control for "any variability").
- adaptive_halt: hop until the node stops changing (uses the per-input halt
  signal = information about m(x)) — the mechanism.
- oracle: exactly m(x) hops (ceiling).
4 preregistered difficulty distributions {uniform, easy_skew, hard_skew, bimodal};
K = round(E[m]) so static and adaptive use equal AVERAGE compute. 8 seeds.

## Confirmation gate
CONFIRMED iff ALL:
1. `|adaptive−static solved-gap − P(m>K)| < 0.02` for every distribution × seed;
2. adaptive > random at equal avg compute (paired CI lower > 0.1) — advantage is
   from USING the input signal, not mere depth variability;
3. adaptive == oracle (halt recovers m(x) exactly);
4. adaptive avg compute == K (compute matched).
Else NOT_CONFIRMED (valid negative).

## Why this rules out the three alternatives
- not capacity: identical operator, identical parameters;
- not compute: identical average hops (K);
- not optimization: the policy is deterministic, zero training;
- remaining cause = information: adaptive uses m(x) via the halt signal; static
  ignores it. The gap is the Jensen gap of allocating a fixed resource under
  heterogeneity, and its SIZE is predicted (P(m>K)), not fitted.
