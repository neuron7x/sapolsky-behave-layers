# PREREGISTRATION — L4b Inferred-Context Boundary (route-decision cost)

**Committed before the run.** Where L4a gave the governor the true context for free
(`c_route=0`, recovery 1.0), this makes the context **inferred** from a noisy observation,
so routing has a real cost and the governor **can fail**. It instantiates the master
inequality `V_realized ≤ oracle_gap − c_route` and the value-of-information bound on the
plasticity mechanism, and maps the failure boundary as a function of `I(C;Z)`.

## Design (frozen)

- **Rewards (real):** measured `U_λ=1[seed, task, group]` from
  `artifacts/wp3-plasticity-v2-confirmatory/raw_runs`. Train seeds 5–12, held-out 13–20.
- **Noisy observation:** each episode draws true context `c ∈ {lexical, relational}`
  uniformly and an observation `z = c` with prob `1−p`, else the flipped label, for a
  **flip probability sweep** `p ∈ {0.0, 0.1, 0.2, 0.3, 0.4, 0.5}`. Mutual information
  `I(C;Z) = 1 − H₂(p)` bits (1.000, 0.531, 0.278, 0.119, 0.029, 0.000).
- **Governor:** softmax policy `π(group | z)` on the OBSERVATION only (never the true
  `c`), REINFORCE with moving-average baseline, reward = the true-context measured utility
  of the sampled arm. 8 controller seeds; report the mean and the worst. The governor may
  learn to route on `z` OR to abstain (pick the best fixed arm, ignoring `z`).
- **Evaluation (held-out):** greedy `π`; realised `= E_{c,z,seed}[U[seed][c][π(z)]]`.
  `recovery(p) = (realised − best_fixed) / (oracle − best_fixed)` (best_fixed and oracle
  as in L4a: 0.5278 and 0.7187, gap 0.191).

## Grounded theory prediction (derived from the measured utilities, NOT fit)

If the governor commits to routing (`z=0→head`, `z=1→attn`), the measured utilities give
**`recovery(p) = 1 − 2.146·p`**, crossing zero at **`p* = 0.466`** (`I* ≈ 0.006 bit`):

| p | 0.0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 |
|---|---|---|---|---|---|---|
| I(C;Z) bit | 1.000 | 0.531 | 0.278 | 0.119 | 0.029 | 0.000 |
| predicted recovery (commit) | 1.000 | 0.785 | 0.571 | 0.356 | 0.142 | −0.073 |

A governor that instead **abstains** at high noise floors recovery at ~0 (never negative).
Which it does is itself a reported behavioral result.

## Decision rule (FROZEN) — this maps a boundary; it is not a capability claim

- **L4B_BOUNDARY_MAPPED** iff ALL hold on held-out:
  (1) `recovery(0.0) ≥ 0.9` (reproduces the given-context L4a result);
  (2) recovery is **monotonically non-increasing** in `p` (increasing in `I(C;Z)`);
  (3) a boundary exists: `recovery(0.5) ≤ 0.10` (no information ⇒ no realisable gap);
  (4) the measured curve tracks the grounded prediction where the governor commits
      (|measured − predicted| ≤ 0.15 for `p ≤ 0.3`), OR the governor demonstrably
      **abstains** (recovery ≥ −0.02 at every `p`, i.e. never routes itself below fixed).
- **L4B_NOT_MAPPED** — monotonicity (2) fails, or `recovery(0.5) > 0.10` (a manufactured
  gap with zero information ⇒ instrument broken), or `recovery(0.0) < 0.9`.

## Scope / prohibited

Tier `SYNTHETIC`. This is a **boundary/route-decision-cost** result (the plasticity analog
of L2b), not a capability advance: it shows the L4 governor's realisable value is bounded
by `I(C;Z)` and vanishes when the context cannot be cheaply inferred. It does NOT establish
real-workload routing, L7 Pareto, energy/latency, or independent replication. It does not
change L4's status; it adds `CWC-L4b-inferred-context` as a SUPPORTED boundary claim.
