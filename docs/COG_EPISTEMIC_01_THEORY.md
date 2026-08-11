# COG-EPISTEMIC-01R — Capability-Bound Epistemic Runtime Theory

## 1. Problem

A causal system can be numerically conservative while remaining semantically unsafe if authority is represented only by free-form strings. A downstream module can accidentally turn `UNIDENTIFIED`, `candidate`, or `survived null` into a stronger state without presenting the evidence that licenses that promotion.

COG-EPISTEMIC-01R therefore treats epistemic authority as an executable protocol, not a label.

## 2. Positive authority chain

The only admitted strengthening chain is

`OBSERVED < PREDICTIVE < ASSUMPTION_CONDITIONAL < INTERVENTION_SUPPORTED`.

The relation is defined only over positive evidence tiers. `FALSIFIED`, `UNIDENTIFIED`, `OOD`, and `ABSTAIN` are absorbing dispositions, not weaker points on the same positive chain. This avoids the category error of ordering “falsified” below “observed” as though more evidence could silently promote the same record back upward.

## 3. Capability theorem

For a parent record `r`, a strengthening transition is admitted only if a capability token `k` is bound to

`(claim_id(r), digest(r), context_scope(r), evidence_class, target_state)`.

Therefore a token issued for a different claim, stale parent digest, or different scope is rejected before authority changes.

The token also binds SHA-256-addressed evidence references. This is an integrity/provenance condition; it is not a cryptographic proof that the evidence is scientifically true.

## 4. Evidence-class separation

The runtime deliberately separates:

- factual observation;
- held-out predictive validation;
- explicit identifying assumptions;
- direct intervention;
- surrogate counterfactual/replay evidence;
- countermodel/falsification/OOD evidence.

In particular, `SURROGATE_MODEL` and `REPLAY_GENERATED` sources cannot mint `DIRECT_INTERVENTION` authority even if a caller labels the payload “do(X)”. This encodes the CSCA-03/05/07 boundary directly in the runtime.

## 5. No truth state

There is intentionally no `TRUE_CAUSAL_MODEL` or unconditional causal-truth state. `INTERVENTION_SUPPORTED` means only that an explicitly scoped operator/context has direct intervention support. It does not erase assumption lineage and does not imply semantic/environmental universality.

## 6. Terminal-state rule

`UNIDENTIFIED`, `FALSIFIED`, `OOD`, and `ABSTAIN` are absorbing for the current record lineage. New evidence may create a new record lineage; it cannot mutate the old terminal record into a positive state. This makes re-opening explicit and auditable.

## 7. Legacy boundary

Historical CSCA/COG artifacts remain immutable string-valued scientific records. The new adapter maps them fail-closed into typed runtime records without rewriting their sealed results:

- `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS -> ASSUMPTION_CONDITIONAL`;
- `IDENTIFYING_ASSUMPTION_VIOLATED -> UNIDENTIFIED`;
- `INSUFFICIENT_INFORMATION_BUDGET -> UNIDENTIFIED`;
- `OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES -> UNIDENTIFIED`.

No adapter emits `INTERVENTION_SUPPORTED` from passive/assumption/countermodel evidence.

## 8. Scope and non-proof

This is a software/epistemic safety theorem about the admitted runtime API. Python code with arbitrary process-memory access can always bypass normal object APIs (`object.__new__`, monkey-patching, interpreter modification). The claim is therefore not “unforgeable against a malicious host”; it is “illegal promotion is impossible through the supported CWC runtime transition API and is mutation-tested/gated.”
