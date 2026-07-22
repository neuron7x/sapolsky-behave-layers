# WP18 — Real-Workload Identifiability PILOT (RESULTS)

**Act:** CWC-ASCEND-2026-01, gates G3/G5/G7. **Prereg:** `2798ea5`, committed before any result.
**Verdict:** `WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY`.
**Class ceiling:** PILOT — estimates gap/variance/MDE/`c_route` only. No architecture claim.

## The decision this triggers
The Act's WP18 kill rule states: *if both real workloads have `G_lo ≤ c_route`, stop architecture
work and publish the negative boundary.* **Both failed. The kill rule fires.**

## Design actually executed
2 distinct real task families × 2 model scales × 2 sequence lengths × 3 seeds = **24 trained
models**, each evaluated on **5 held-out eval shards** → 60 replicate (seed × shard) units per
workload. Corpora split deterministically by SHA-256 **per source file**; contamination check
clean for both (no shared files, no eval text in train).

| workload | family | train | eval shards |
|---|---|---|---|
| `prose` | English prose (repo docs) | 158,117 B / 37 files | 5 (6.5–51 KB) |
| `code` | Python source | 908,564 B / 167 files | 5 (59–160 KB) |

## Result
| workload | `G_lo` (λ=0) | `G_lo` (λ=0.3) | `c_route` (measured, WP17) | passes G3 |
|---|---|---|---|---|
| prose | −0.2004 | −0.1968 | 0.0006 | **No** |
| code | −0.1709 | −0.1543 | 0.0006 | **No** |
| **positive control** (synthetic AC1) | **+0.6195** | — | — | ✅ certifies |

The certificate works — it certifies the synthetic mechanism in the same run. The real-workload
null is therefore **real**, not an instrument failure.

## Why: there is no context × resource interaction (the mechanism of the negative)
The preregistered surface probe found the **modal best K is 2 for *every* difficulty bucket** in
both workloads (easy = med = hard = 2). Adaptive allocation has nothing to allocate: more compute
helps all difficulty levels roughly uniformly up to K=2 and stops helping after. The oracle
therefore collapses onto a single fixed policy, and the gap collapses with it.

## Variance, MDE and what a confirmatory study would cost
| workload | n (seed×shard) | mean plug-in gap | sd | MDE @ pilot n | n needed (plug-in effect) |
|---|---|---|---|---|---|
| prose | 60 | +0.0011 | 0.0020 | 0.0007 | 26 |
| code | 60 | +0.0012 | 0.0023 | 0.0008 | 27 |

Honest nuance: a **tiny** positive plug-in gap (~0.001 nats) does exist and would be *statistically*
detectable with ~26 replicate units. It is not certifiable and not useful:
- The certificate's bias+deviation correction at this noise level is ≈0.2 nats — roughly **180×**
  the observed effect. Shrinking it below the effect needs ~180² ≈ 3×10⁴ times more replicates
  (order **10⁶** replicate units) under √n scaling. Practically unreachable.
- The effect (~0.001 nats) is the same order as the **measured** route cost (0.0006). Even taken at
  face value, paying for the decision consumes it.

## Cumulative status of the real-data axis
This is the **third independent real-data negative**, now with the strongest design of the three:

| WP | difficulty signal | data | outcome |
|---|---|---|---|
| WP6 | unigram surprisal | 66 KB prose | not identifiable |
| WP14 | bigram surprisal | 66 KB prose | not identifiable (robust to signal) |
| **WP18** | bigram surprisal | **2 families, 1.07 MB, 5 eval shards each, 2 scales × 2 lengths** | **not identifiable (kill rule)** |

Per the preregistration, no fourth difficulty signal will be hunted: three independent negatives
across two signals, two task families, two scales and two sequence lengths is a **boundary**, not an
instrument problem.

## Scope and what this does NOT say
- It does **not** say adaptive compute never helps real LMs. It says that on **byte-level models
  trained from scratch at this scale**, per-token difficulty does not induce a certifiable
  compute-allocation gap.
- **L7** (real compute-equivalent Pareto at scale, with MoD/MoE baselines) remains `NOT_TESTED` and
  cloud-blocked. This pilot is precisely the Act's instrument for deciding whether to spend on it —
  and its answer, at reachable scale, is **do not spend yet**.
- No architecture claim of any kind is raised by this WP.
