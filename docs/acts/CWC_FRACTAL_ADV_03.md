# CWC-FRACTAL-ADV-03 — Topology Semantics / Execution Matrix

**Status:** FROZEN BEFORE MATRIX EXECUTION  
**Scope:** archived CWK reference implementation only  
**Scientific ascension authority:** none  
**VIA authority:** none

## 1. Purpose

Attack two remaining semantic shortcuts directly:

1. whether the archived local/global attention topology warrants any `fractal` interpretation;
2. whether controller/budget telemetry corresponds to physical conditional execution across more
   than one seed, shape and controller policy.

The act is failure-seeking. A positive diagnostic cannot establish cognition, fractality or useful
adaptive compute.

## 2. Topology audit

Use the archived `local_global_mask` implementation itself and the archived smoke configuration.
Evaluate sequence lengths `8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256`.

Record exact directed edge count, density, wiring cost, undirected projected diameter and a log-log
edge-count scaling slope. Verify the archived implementation against the exact edge formula for the
frozen case `global_tokens=1`:

`E(n,w) = (w+2)n - (w+2)(w+1)/2`, for `n>w+1`.

A graph-fractal claim is **not identifiable** if the undirected projection has diameter <=2 because a
single global hub collapses graph-distance scale. Linear sparse edge scaling alone is not accepted as
fractal evidence.

## 3. Execution matrix

Prespecified model seeds: `101, 211, 307`.

Prespecified shapes:

- `(1, 8)`
- `(2, 12)`
- `(4, 12)`
- `(5, 24)`

For each seed/shape, test controller modes `learned`, `random`, `inverted`, `static` under:

- unconstrained active tokens, depth=2;
- half active-token budget, depth=1;
- quarter active-token budget, depth=1.

Forward hooks count rows actually presented to shared/routed experts, attention query tokens and output
projection. Controller gates must change under at least one intervention, yet physical expert work must
fall if the gates are real compute governors.

Additional probes:

- `max_active_experts=top_k` versus `num_experts` on identical inputs;
- attention budgets set below the known topology density, with attention-call hooks active;
- memory retrieval after deterministic memory population: record query rows entering `memory.read`
  before the controller's per-token memory gate.

## 4. Acceptance / falsification semantics

- Gate telemetry changes while expert rows remain invariant => `SEMANTIC_GATE_ONLY`.
- Attention executes before an over-density exception => `POST_EXECUTION_GUARD_NOT_GOVERNOR`.
- Legal `max_active_experts` values above `top_k` do not change routes =>
  `LOWER_BOUND_CHECK_NOT_ACTIVE_EXPERT_GOVERNOR`.
- Memory retrieval receives all query rows before sparse controller memory gating =>
  `POST_RETRIEVAL_MEMORY_GATE`.
- Undirected topology diameter <=2 over the tested scaling range => graph-distance fractal dimension
  lacks a usable scale range in this reference topology.

No wall-clock threshold is claim-bearing in this CPU environment.
