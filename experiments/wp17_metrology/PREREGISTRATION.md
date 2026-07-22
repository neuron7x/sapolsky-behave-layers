# WP17 — Physical Metrology & Complete Cost Accounting (PREREGISTRATION)

**Act:** CWC-ASCEND-2026-01, gate **G2**. Preregistered BEFORE running (separate commit).
**Target mechanism:** the real trained AC1 `RecurrentModel` (weight-tied recurrent block) — the same
mechanism WP15's compute-Pareto claim rests on. **Class ceiling:** metrology + a kill-test on an
existing claim. Raises no new mechanism tier; may NARROW `CWC-L7s-synthetic-pareto`.

## Why
WP15 measured compute as `FLOPs ∝ K iterations` and charged **nothing** for the controller that
chooses K. Act §8 forbids excluding controller/dispatch cost from compute accounting. Until the
route-decision cost is *physically measured*, `V_net = ΔQ − C_compute − c_route` is NOT_IDENTIFIED.

## Questions & frozen decision rules

**Q1 — FLOP-ledger fidelity.** Does the analytical FLOP ledger match a profiler measurement of the
same forward? **Metric:** relative error `|analytic − profiler| / profiler` per operating point
K ∈ {1,2,3}. **PASS iff ≤ 1%** at every K (Act WP17 acceptance).

**Q2 — Physical route-decision cost (the point of this WP).** Measure the AC2 controller's own
forward cost (FLOPs and wall-time) and express it as a fraction of one model forward:
`rho_flops = controller_FLOPs / model_FLOPs(K=1)`, likewise `rho_time`. Reported, not gated —
this is the estimand, not a hypothesis.

**Q3 — KILL-TEST on WP15 (primary falsifier).** Recompute the WP15 compute-equivalent Pareto with
the **physically measured** controller cost charged to the adaptive arm at matched total compute
(fixed-K arms pay no controller cost; adaptive pays `rho_flops` per decision).
- `PARETO_SURVIVES_PHYSICAL_ROUTE_COST` iff adaptive advantage at matched *total* compute
  (model + controller) remains **> 0.05** — the same margin WP15 preregistered.
- `PARETO_KILLED_BY_ROUTE_COST` iff the advantage drops to **≤ 0** — WP15's claim would be
  re-registered NOT_SUPPORTED.
- Anything in `(0, 0.05]` → `PARETO_NARROWED_BY_ROUTE_COST` → `CWC-L7s` becomes SUPPORTED_NARROWED.
- **No post-hoc redesign**: this rule is frozen here, before the measurement exists.

**Q4 — Instrumentation overhead.** Alternating `OFF → COUNTERS → COUNTERS → OFF` windows after a
fixed warm-up, CUDA synchronisation only at window boundaries. **PASS iff median ≤ 1% and
p95 ≤ 2%** of baseline step time.

**Q5 — Latency stability.** After warm-up, repeated-run coefficient of variation of step latency.
**PASS iff CV ≤ 3%.**

**Q6 — Energy.** Energy must remain `INSTRUMENT_INVALID` / unavailable (no validated meter on this
host). **FAIL if any non-`available=False` energy value is synthesized.**

## Procedure
Fixed seed; warm-up discarded; N=30 measured repetitions per operating point; `torch.profiler`
(`with_flops=True`) for Q1; CUDA sync at window boundaries only. Deterministic given (seed, host).
Host/GPU/driver/CUDA/torch recorded in the verdict.

## Kill rules (falsifiers)
- FAIL Q1 if ledger error > 1% → the FLOP accounting used by every prior compute claim is wrong.
- Q3 is a genuine kill-test on my own prior positive: a large physical `c_route` **must** narrow or
  kill `CWC-L7s`, and that outcome will be registered, not re-run away.
- FAIL Q6 if a zero-energy value is reported as available.

## Prohibited extrapolations
- Real-workload (L7) compute-equivalent Pareto — unchanged, still cloud-blocked.
- Energy efficiency of any kind.
- Generalisation of measured `rho` beyond this model/host/batch regime.
