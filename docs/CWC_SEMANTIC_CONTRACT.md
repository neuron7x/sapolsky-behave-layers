# CWC Semantic Contract — the name must not outrun the referent

Status: NORMATIVE. This document governs how capability terms may be used in
all CWC docs, code, commits, and claims. It applies the use/mention discipline
already enforced elsewhere in this project's gates.

## The semiotic state of "Cognitive Wiring Core" (2026-07-16)

A sign has three vertices (Peirce / Ogden–Richards):

| Vertex | CWC today |
|---|---|
| **Symbol** (the name) | "Cognitive Wiring Core" — exists in docs and repo names |
| **Referent** (the thing) | an adaptive compute-control mechanism — **DOES NOT EXIST YET** |
| **Interpretant** (what gives claims meaning) | the WP-1 instrumentation + evidence pipeline — **EXISTS, verified** |

"CWC" is currently a *floating signifier*: a promise, not a denotation. What
exists is the interpretant machinery — the apparatus that will make future
claims about the referent *meaningful* (measurable, falsifiable, reproducible).
Building the interpretant before the referent is the correct
falsification-first order; the hazard is semantic inflation — using capability
terms as if they already denote. This contract prevents that.

## Rule

A capability term below may be used in the **denoting** mode (as a thing that
exists) only when its tier is `SUPPORTED`. Until then it may only be
*mentioned* (quoted, planned, specified). Every claim that uses a term in
denoting mode MUST cite the evidence artifact that moved it to `SUPPORTED`.

Tier ladder (per term): `ABSENT → SPECIFIED → IMPLEMENTED → MEASURED → SUPPORTED`.
A tier moves only forward via its gate; a failed falsification test moves it
back and the failure artifact is committed (negative results are landed, not
discarded).

Every gate MUST include a positive control — a deliberately broken/ablated
variant that the test provably rejects. A test that cannot fail is not a test.

## Term registry

All six terms below: tier = **ABSENT** (2026-07-16).

### 1. `learnable router`
- **Operational definition:** a module with trainable parameters whose per-token
  routing decisions are updated by task-loss gradient (not a fixed heuristic).
- **Measurement binding:** `cwc/instrumentation/routing.py` counters
  (active_tokens/blocks/experts per step) + training manifest seed/config.
- **Falsification criterion:** ablation — freeze the router at initialization
  and retrain; if task metric of the frozen-router model is inside the
  bootstrap CI of the trained-router model, the term is VOID (the routing is
  decoration, not learning).

### 2. `memory control`
- **Operational definition:** a learned read/write policy over persistent state
  that survives across contexts and measurably conditions computation.
- **Measurement binding:** state-size and access counts via the event buffer;
  determinism gate on state serialization.
- **Falsification criterion:** memory-ablated (state zeroed each context) model
  matches the full model within CI on the preregistered task suite → VOID.

### 3. `dynamic depth`
- **Operational definition:** per-token variable number of executed blocks,
  decided at inference time by a learned criterion.
- **Measurement binding:** per-token FLOPs via `cwc/instrumentation/flops.py`
  ledger; depth histogram must be an evidence artifact.
- **Falsification criterion:** depth distribution degenerate (variance ≈ 0 —
  i.e., it always picks the same depth), OR measured FLOPs saving smaller than
  the routing/measurement overhead → VOID.

### 4. `structural plasticity`
- **Operational definition:** topology edits (grow/prune connections or blocks)
  driven by a utility signal during or between training phases.
- **Measurement binding:** structure snapshots hashed into the manifest;
  edit-log as evidence artifact.
- **Falsification criterion:** structural edit-distance from initialization is
  zero, OR random (utility-blind) edits of equal budget reach the same task
  metric within CI → VOID.

### 5. `task utility`
- **Operational definition:** preregistered task suite, metric deltas vs the
  unmodified nanochat baseline, seeds and configs frozen before the run.
- **Measurement binding:** `bootstrap_ci` from `cwc/instrumentation/stats.py`;
  evidence bundle with SHA256SUMS.
- **Falsification criterion:** 95% bootstrap CI of the delta includes 0 → NOT
  SUPPORTED (and that verdict is committed).

### 6. `Pareto advantage`
- **Operational definition:** on the (task metric, compute cost) plane — cost =
  FLOPs and/or energy from the WP-1 meters — no baseline configuration
  dominates the CWC configuration, and CWC dominates at least one baseline.
- **Measurement binding:** FLOP ledger + energy meter + task-utility artifacts,
  all from the same manifested runs.
- **Falsification criterion:** any baseline point that dominates (≥ quality at
  ≤ cost, one strict) → NOT SUPPORTED.

## Naming consequences

- Repo/docs may keep "CWC" as a *project* name (a proper noun for the
  programme), but no README, report, or commit message may assert CWC as an
  existing mechanism until ≥1 term above is SUPPORTED.
- The honest current description is: "a verified measurement substrate for a
  future adaptive compute controller" (see `CWC_QUALITY_REPORT.md`, scope
  section).
- Known open honesty items inherited from WP-1: overhead gate
  `BLOCKED_BY_MEASUREMENT_OVERHEAD`; nanochat integration
  code-complete-but-not-runtime-verified.
