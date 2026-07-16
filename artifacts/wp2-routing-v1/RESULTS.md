# WP-2 Routing v1 — RESULTS

Pilot, 3 seeds {0,1,2}, `claimable = no` (Act G1). Task: in-context
associative recall, n_pairs=6, L=8 blocks, K=4 budget. Lower query-position CE
is better. Full data: `raw_runs/`, stats: `statistics/analysis.json`.

## Headline verdict
```
ROUTING_NOT_SUPPORTED  (mechanism: ROUTER_COLLAPSE)
```
The learned controller, free to pick any 4 of 8 blocks per sequence, converged
to a **constant** policy — always blocks [0,1,2,3] — for every sequence
(per-layer utilization `[1,1,1,1,0,0,0,0]`), **identical to the fixed-depth
control**. It did not learn to route adaptively. Learned routing beat *random
per-sequence* selection but showed **no advantage over a frozen (untrained)
controller or a static fixed-depth truncation**. At this scale and task,
learned *adaptive* compute allocation does not outperform static allocation.

## Per-config quality (mean best query-CE over 3 seeds)
| Config | active blocks | mean query-CE | interpretation |
|---|---:|---:|---|
| dense (E0) | 8 | 0.00599 | quality ceiling (all blocks) |
| random (E1) | 4 | 0.02008 | per-sequence random K — worst |
| frozen (E2) | 4 | 0.00257 | untrained controller, fixed selection |
| learned (E3) | 4 | 0.00387 | **candidate** |
| fixed_depth (E4) | 4 | 0.00433 | static first-K |

## Paired causal tests (learned − control, 95% bootstrap CI; negative = learned better)
| Comparison | mean Δ | 95% CI | learned better? |
|---|---:|---|:--:|
| learned − random | −0.01621 | [−0.02031, −0.01398] | **YES** (CI < 0) |
| learned − frozen | +0.00130 | [−0.00650, +0.00556] | NO (straddles 0) |
| learned − fixed_depth | −0.00045 | [−0.00200, +0.00137] | NO (straddles 0) |
| learned − dense | −0.00212 | [−0.00727, +0.00388] | NO (matches dense at ½ blocks) |

Act H3 requires learned > random **AND** learned > frozen for
`ROUTING_SUPPORTED`. The first holds; the second fails. Verdict is
NOT_SUPPORTED, refined to ROUTER_COLLAPSE because the learned policy is
constant across sequences.

## VERIFIED
- Compute parity across the four K-configs within 1% (identical K=4 active
  blocks; controller FLOPs 67 584 vs backbone ~2.37e8 = 0.03%). `parity=True`.
- Zero hard-budget violations across all K-configs and seeds.
- Learned routing is strictly better than *random per-sequence* selection
  (entire paired 95% CI below 0) — consistency of block choice matters.
- Learned controller **collapsed** to a static [0,1,2,3] selection (identical
  to fixed_depth), for all seeds.
- A 4-block static selection matches the 8-block dense model on this task
  (learned−dense CI straddles 0) — i.e. half the blocks suffice here.

## NOT_SUPPORTED
- H1: learned allocation does NOT beat frozen or fixed-depth controls; the
  advantage over random comes from *consistent* (not *learned*, not *adaptive*)
  block selection.
- H2: the learned policy is NOT a stable non-collapsed adaptive policy — it
  collapsed to a constant selection (no per-sequence adaptivity).

## NOT_TESTED
- ≥5-seed claim tier (this is a 3-seed pilot; direction is unambiguous but
  formal claim status is PILOT).
- Token-level routing, deeper/harder tasks where K is a binding constraint,
  transfer/adaptation/forgetting (Act G5, deferred).
- Energy (INSTRUMENT_INVALID upstream — excluded by design).

## Honest boundary / why the null is informative but limited
1. **K=4 was near-sufficient.** A static 4-of-8 selection already matches
   dense (0.004 vs 0.006), so the budget barely constrained the task — leaving
   little headroom for *adaptive* routing to demonstrate value. A stronger
   test needs a more binding budget (smaller K) or a task requiring
   input-dependent depth.
2. **Per-sequence pooled routing has weak signal.** The controller input
   (mean-pooled embedding) is nearly constant across these structurally similar
   sequences, so it cannot differentiate them → it rationally collapses to a
   fixed top-K. Token-level or content-richer routing signal is the next lever.
3. This is a VALID experiment (qualified instrument, exact parity, working
   controls, deterministic eval, zero budget violations) returning an honest
   negative — not an invalid one. Per Act §17 this is a legitimate completion.

## Next decisive experiment
Re-run at a **binding** budget (K=2 of 8) on a task with genuinely
input-dependent required depth, and add a per-token routing variant, to test
whether adaptivity ever beats static selection when the budget actually bites.
