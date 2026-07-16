# WP-2 Routing v1.1 — RESULTS (binding budget K=2, heterogeneous task, 5 seeds)

Claim tier (5 seeds {0..4}). Task: mixed recall/copy, per-sequence type,
K=2 of 8 blocks. Lower answer-CE is better. Data `raw_runs/`, stats
`statistics/analysis.json`. Preregistered: `../../experiments/wp2_routing_v1/PREREGISTRATION_v1_1.md`.

## Headline verdict
```
ROUTING_NOT_SUPPORTED_COLLAPSE
```
The learned controller again collapsed to a **constant, non-adaptive** policy
(`routing_divergence_copy_vs_recall ≈ 0`) — it routed COPY and RECALL
sequences to the **same** blocks, despite the task being purpose-built so that
routing by type could help. H2' (adaptivity) is **falsified at 5 seeds**.

## Per-config (mean over 5 seeds)
| Config | active | answer-CE | acc | acc RECALL | acc COPY | route div (copy vs recall) |
|---|---:|---:|---:|---:|---:|---:|
| dense | 8 | 0.372 | 0.843 | 0.676 | 1.000 | ~0 |
| random | 2 | 0.0359 | 0.993 | 0.985 | 1.000 | 0.107 |
| frozen | 2 | 0.00282 | 0.999 | 0.999 | 1.000 | ~0 |
| learned | 2 | 0.00142 | 1.000 | 0.999 | 1.000 | **~0 (collapsed)** |
| fixed_depth | 2 | 0.00135 | 1.000 | 1.000 | 1.000 | ~0 |

## Paired causal tests (learned − control, 95% bootstrap CI; negative = learned better)
| Comparison | mean Δ | 95% CI | learned better? |
|---|---:|---|:--:|
| learned − random | −0.0344 | [−0.0439, −0.0256] | **YES** |
| learned − frozen | −0.0014 | [−0.0053, +0.0025] | no (straddles 0) |
| learned − fixed_depth | +0.00007 | [−0.0014, +0.0015] | no (straddles 0) |
| learned − dense | −0.370 | [−0.736, −0.0055] | YES (dense unstable) |

## Verdict logic
`ROUTING_SUPPORTED` needs learned > all static controls AND adaptive
(route_div > 0.1). Learned beats random but is indistinguishable from frozen
and fixed_depth, and route_div ≈ 0 → collapse. Verdict:
NOT_SUPPORTED_COLLAPSE. Parity within 1%, 0 budget violations → VALID.

## Three robust findings (now across 10 seeds and two task regimes)
1. **Learned routing collapses every time.** v1 (K=4, homogeneous):
   constant [1,1,1,1,0,0,0,0]. v1.1 (K=2, heterogeneous, adaptivity-favoring):
   route_div ≈ 0. The controller never learned per-input allocation.
2. **Consistency, not learning, is the only edge.** Learned reliably beats
   *random per-sequence* selection (both regimes) but never beats *frozen* or
   *fixed-depth* static selection. Confirmed at claim tier (5 seeds).
3. **Surprising inversion — K=2 static beats 8-block dense.** Dense fails to
   learn RECALL on 2/5 seeds (acc 0.68 mean, unstable), while the constrained
   K=2 models converge reliably to acc ≈ 1.0. Fewer active blocks gave *more
   reliable* optimization here — an unexpected, honestly-reported result, not
   a routing advantage.

## Why the budget still did not bind (honest boundary)
Even at K=2, any 2 blocks (random, frozen, fixed, or collapsed-learned) solve
both COPY and RECALL — the d=128/8-block backbone is over-capacity for this
task, so block *identity* barely matters. To force adaptivity to pay, a future
experiment needs a regime where a single fixed 2-block choice provably CANNOT
serve both sub-tasks (e.g. sub-tasks needing disjoint, non-substitutable
mechanisms, or K=1), and/or token-level routing. This is a limit of what a 4
GiB laptop scale can currently demonstrate — reported, not hidden.

## Bottom line for H_CWC
Across two preregistered regimes, **learned adaptive compute allocation shows
no advantage over static allocation** and consistently collapses to a
non-adaptive policy. At this scale, the central CWC routing premise is
NOT_SUPPORTED. This is a valid, claim-tier negative (Act §17), and it directly
constrains the RCFR programme: adding role-modulation atop a router that will
not route adaptively is unjustified until a binding regime is found.
