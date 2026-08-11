# COG-SELF-01 — Autonomous Decision-Relevant Falsification Governor

**Date:** 2026-08-11  
**Preregistration commit:** `ee99a9e732e3b4fc408f80a9a3ce71d3178717d6`  
**Implementation commit:** `a77927568c246f91c04bd0b239b7ca625f851a74`  
**Verdict:** `AUTONOMOUS_DECISION_RELEVANT_FALSIFICATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `SYNTHETIC_SELF_FALSIFICATION_SAFETY_SELECTION_PRIMITIVE_ONLY`

## Question

Can the cognitive runtime attack its own load-bearing beliefs without turning
self-evaluation into self-authorization? COG-SELF-01 composes the existing typed
memory, dependency ledger, proof-carrying plan, surviving-world representation and
COG-INFO-02 decision-relevant information governor. The new primitive selects a bounded
falsification attack only when the represented ambiguity can change the current action.

## Frozen execution

Two fresh cohorts were executed independently:

- PRIMARY seeds `710811..710938`;
- REPLICATION seeds `810811..810938`;
- `12` frozen families S0-S11;
- `128` cases/family/cohort;
- `1536` cases/cohort;
- `3072` total confirmatory cases;
- `alpha=0.01`, `target_power=0.95`, robust action margin `0.05`.

The implementation commit was frozen before the confirmatory run. Generation and replay
produced the same row hash:
`cf6b6a2e3704350e0421dc0abd304fe14f02aea800380d81d4aa4d6607aa4863`.

## Confirmatory result

Every S0-S11 family passed `128/128` in PRIMARY and independently `128/128` in
REPLICATION. Each cohort recorded:

- runtime errors: `0`;
- false spend: `0`;
- irrelevant-memory attack selections: `0`;
- uncertified attack selections: `0`;
- stale-plan acceptances: `0`;
- permutation disagreements: `0`;
- survival authority promotions: `0`;
- negative-target violations: `0`;
- stale/unbound outcome acceptances: `0`;
- negative-propagation checks: `256/256`.

The negative-propagation checks cover S6 plus all S10 cases whose outcome is evaluated;
they verify that a falsified load-bearing parent or invalidated assumption retracts the
bound dependency closure while preserving ledger invariants.

## Load-bearing separations

### S0 — unresolved model identity is not a compute license

The worlds retained distinct identities and a high-rate cheap probe was available, but
all worlds recommended the same margin-separated action. The governor spent nothing.
This is the central distinction between causal/model uncertainty and immediate decision
uncertainty.

### S2 — nuisance information does not dominate

A probe with high information about a same-decision world but weak information against
the action-flipping world lost to the probe with the stronger certified
cross-decision rate. Selection is therefore on the decision quotient, not total model
information.

### S4/S11 — stale authority fails closed

A plan whose bound memory was retracted before selection was never accepted. A selected
attack whose load-bearing ledger changed before outcome application was also rejected;
no additional mutation occurred. The selected decision is digest-bound to the current
plan, world set and transitive load-bearing memory graph.

### S6/S10 — self-falsification is monotone-negative

A successful negative test can retract a selected load-bearing memory or invalidate a
selected assumption and let the existing dependency ledger propagate the loss of
authority. `SURVIVED` and `INCONCLUSIVE` have no promotion path. The API contains no
operation that mints stronger epistemic state, consolidates new causal memory, or rewrites
frozen evidence.

## What this result does not show

This result is a synthetic runtime safety/selection qualification. Certified information
rates, world completeness, utilities and action maps are supplied by the harness. The
experiment therefore does not establish that arbitrary real observations provide valid
information-rate lower bounds, that the admitted world set contains the environment's
true mechanism, or that self-falsification discovers semantic causal truth.

The exact selection behavior is also not evidence of an autonomous scientist: the
admissible attacks and their certificates are inputs. What is qualified is the
fail-closed composition and the monotone-negative authority boundary.

## Promotion boundary

Still forbidden:

- semantic causal truth;
- autonomous scientific-discovery claims;
- natural-language or real-model transfer;
- production active-control authority;
- matched-compute architecture advantage;
- external independent replication;
- flagship-result promotion.

Novelty remains `UNKNOWN_OVERLAP_CONCEDED`.

## Next hard gate

The synthetic cognitive-core sequence is now closed through self-falsification. The next
load-bearing gate is external validity: use a frozen public/matched-compute causal-authority
benchmark on real-model task families, with independently authored instances and
contamination controls, and test whether decision-relevant acquisition lowers false
causal authority / wasted acquisition without reducing decision utility. A later
third-party reproduction remains mandatory for flagship promotion.
