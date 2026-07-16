# WP-3 Plasticity (AMG) — oracle-gap RESULTS. VERDICT: `PLASTICITY_BENCHMARK_NOT_IDENTIFIABLE`

5 seeds, preregistered (`../../experiments/wp3_plasticity_v1/PREREGISTRATION.md`).
Data `oracle-gap/raw_runs/`, stats `oracle-gap/analysis.json`.

## Verdict
The plasticity benchmark is **not identifiable** at this scale: a per-task
oracle plasticity allocation gives **no advantage** over a fixed allocation
(mean oracle gap = **0.0001**, 95% CI [2.4e-5, 9.8e-5] — effectively zero). Per
spec §11.4/§21 this **blocks** training a learned metaplasticity governor. It is
the disciplined fail-closed outcome, not a failure of the AMG idea.

## Per-task utility (mean over 5 seeds), utility = new_acc − retention_drop
| Task | attn | mlp | head | embed | oracle group |
|---|---:|---:|---:|---:|---|
| lexical (relabel) | 0.058 | 0.058 | 0.058 | 0.000 | attn/mlp/head (tied) |
| relational (shift) | **0.182** | −0.397 | 0.178 | −0.170 | attn |

## Why it is not identifiable — two clean structural findings
1. **Substitutable groups.** Lexical relabel is solved equally (new-acc 1.00) by
   attention, MLP and head — the residual stream lets any expressive group
   remap tokens. Only position-*mixing* (attention) is structurally unique
   (relational shift: attn 1.00 vs mlp/head ≈ 0.2). So there is exactly ONE
   structurally-necessary axis (attention), not a per-task-varying optimum.
2. **Task–base conflict destroys retention regardless of locus.** Lexical
   relabel is output-incompatible with the identity base, so EVERY group that
   learns it forgets the base fully (retention drop ≈ 0.94). There is no "safe"
   plasticity locus, because the conflict is in the objective, not the weights.

Consequently attention is the universal best-fixed allocation (oracle choice for
relational, tied-best for lexical), so fixed-attn ≈ oracle → gap ≈ 0.

## What DID pass (verified infrastructure — Gates B & F)
- **Parameter-group registry (Gate B):** 100% parameter coverage, 0 duplicate
  assignments, deterministic group ids (checksum stable across re-inits).
- **Plasticity-aware optimizer (Gate F):** zero mask → parameters byte-identical;
  full mask → numerically equivalent to plain AdamW; budget violation raises;
  inactive groups guaranteed unchanged even under the base optimizer's weight
  decay. 5 core tests pass.

## Honest boundary and next step
This mirrors the routing-v1 lesson exactly: a controller may not be trained on a
benchmark that cannot discriminate its decisions. To make plasticity
identifiable one would need tasks that (a) COEXIST with the base (task-conditional
behavior, e.g. a task token + per-task adapter capacity) so a "safe" locus
exists, and (b) genuinely differ in which group is optimal. Constructing that is
non-trivial and is the honest prerequisite before any AMG governor claim —
exactly what §11.4 protects against skipping. The learned governor (Phases I–J),
the 18 baselines (Phase K) and the causal interventions (Phase L) remain BLOCKED
behind this gate.

## Prohibited wording (spec §22)
No "CWC adaptively protects knowledge", "solves catastrophic forgetting", or
"self-directed growth". Permitted: "CWC contains an experimental group-level
plasticity optimizer and registry; the plasticity benchmark was not identifiable
at this scale, so no governor was trained."
