# CNEH-EXP-04E — frozen EXP04D trace attribution

Status: retrospective diagnostic, not prospective confirmation. This protocol is committed before implementing the new reductions; aggregate EXP04D results were already known. No new cohort outcomes, no parent rerun/tuning, no controller efficacy claim.

## Input boundary
Exactly EXP04D targeted workflow run 45262910203, artifact 14862245545, head 5a6920609579f87008affe8a2bf90b8b8e8e9ac2, archive SHA-256 2cdc9b23dc7521368dc54c63ea91009ae83c7ad05307ca082a54d46225bd5615. Validate archive and inner SHA256SUMS, expected file roster, frozen implementation digests, seed/arm roster and complete 3201-row traces; refuse invalid/incomplete worlds. Use the existing EXP04D and EXP04C code read-only. Output a separate immutable deterministic JSON report; no modification of original evidence.

## Primary reductions
For every OOD segment and adaptive arm, every observation t corresponds to transition t-1. Recompute residual/support from observed conductances and previous source bits. Recompute an evaluator-only full-spike support with previous true bits, identical conductance observations. Validate true-mode containment and observed support superset of full-bit support. For each of three false modes partition opportunity into exactly one of:
- NO_SPIKES: both actual source groups silent (no discriminating signal).
- ALIAS: nonzero source activity but true and false modes predict identical integer arrival counts.
- ERASURE_BLOCKED: unequal predicted counts, false mode still in observed support.
- OBSERVED_EXCLUSION: unequal predicted counts, false mode excluded by observed support.
The first two are non-identification on the realized input, not proof of physiological fatigue. Since residual bands do not overlap, full-bit support must equal the modes predicting the actual integer arrival count. Report counts by mode, arm, seed, and segment, not survivor averages.

At evaluator-known segment boundaries restart an intersection from ALL, separately for observed and complete spike supports. Report first singleton completion and first 20-consecutive correct singleton completion. This is a privileged same-mode information ceiling on the realized trajectory, NOT an implementable online policy or counterfactual plant rollout. Compare actual epoch support to observed segment intersection: stale exclusions (true mode absent), re-expansion events after scheduled renewal and contradictions, and count of ticks retaining false modes already excluded by segment history. Do not attribute all differences causally to expiry; epoch boundaries use hidden information only in diagnostics.

For each ambiguous decision, compute structural discrimination scores for both groups and record tied/untied selection, group-specific active probe exposure, maximum consecutive same-group probe streak, and actual next-observation source spikes (one-transition alignment; do not interpret conditional spike rate as causal). Count segments in which a group capable of discriminating a remaining pair is never actively probed. Report group-level source spike counts in probe vs non-probe transitions, including zero-spike transitions. No biological adaptation mechanism inferred without direct perturbation.

For every reachable segment and all arms measure actual goal-band occupancy and longest continuous in-band run; for adaptive arms separately count correct singleton occupancy and overlap with goal band. Oracle band occupancy is diagnostic, not proof of attainable optimal control. Preserve disconnected tracking and no-change contradictions separately. No favorable thresholds; instrument gate requires all invariant checks and deterministic replay.

## Follow-on (not qualified by this analysis)
Only after diagnostics, register a distinct prospective controller cohort and matched-effort alternating comparator; bounded observation-only excitation scheduling, evidence-conditioned progress, explicit abstention, stale-set handling, actual source response, disconnected states, control recovery and effort reported. Preserve no-leak boundary, immutable parent evidence, and scientific promotion BLOCKED. No external replication or physical cost claim.
