# COG-MEMORY-01 — Assumption-Aware Epistemic Memory Theory

## Scope

This module asks a narrow software/cognitive question: once CWC has a typed epistemic
record, under what conditions may that record be consolidated into reusable memory
without silently upgrading its authority?

It does **not** test whether a causal model is true. It tests whether memory preserves
the authority boundary already established by the epistemic layer.

## Memory object

A memory record is not a bare proposition. It binds:

`claim + context + epistemic_record_digest + epistemic_state + assumptions + evidence_hashes + countermodels + dependencies + revision lineage`.

The binding is immutable. A later stronger epistemic record creates a new memory
version; it cannot mutate the old record in place.

## Consolidation rule

The admissible policy is:

- `OBSERVED` -> active factual memory, noncausal;
- `PREDICTIVE` -> active predictive memory, noncausal;
- `ASSUMPTION_CONDITIONAL` -> quarantined, noncausal;
- `INTERVENTION_SUPPORTED` -> causal-capable only if the surviving countermodel set is
  empty, all dependencies are active, and no bound assumption has been invalidated;
- `UNIDENTIFIED`, `FALSIFIED`, `OOD`, `ABSTAIN` -> no active causal consolidation.

Thus causal usability is a conjunction, not a state-name lookup:

`causal_usable = INTERVENTION_SUPPORTED AND no_countermodels AND assumptions_valid AND dependencies_active`.

Even then the authority remains operator/context scoped; it is not semantic or
unconditional causal truth.

## Retraction closure

Let the dependency graph contain an edge `m_j -> m_i` when memory `m_i` depends on
`m_j`. If a parent memory is retracted, every reachable dependent memory must be
retracted. Likewise, invalidating an assumption retracts every memory carrying that
assumption and the transitive closure of their dependents.

This gives a monotone safety property: invalid evidence can reduce reusable authority,
but cannot strengthen it.

## Countermodel veto

A surviving countermodel is first-class memory debt. An `INTERVENTION_SUPPORTED`
record with a nonempty countermodel set is not active causal memory. This prevents a
strong local intervention label from erasing unresolved model-class ambiguity.

## Event/provenance integrity

Every consolidation, retraction and assumption invalidation appends a hash-chained
`MemoryEvent`. Historical versions remain in the ledger. This is provenance integrity,
not tamper-proof security against an adversary controlling the Python interpreter or
process memory.

## What COG-MEMORY-01 can and cannot establish

It can establish a fail-closed software invariant: through the supported API, memory
cannot silently turn observational, predictive, assumption-conditional, terminal,
legacy-string or surviving-countermodel states into active causal memory, and invalid
parents/assumptions propagate retraction.

It cannot establish causal truth, semantic correspondence, planning utility, replay
benefit, active-control safety, large-model transfer, or external independent
replication.
