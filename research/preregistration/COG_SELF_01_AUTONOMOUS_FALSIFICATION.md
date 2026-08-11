# COG-SELF-01 — Autonomous Decision-Relevant Falsification Governor

Date frozen: 2026-08-11
Status: PREREGISTERED / NO CONFIRMATORY COG-SELF-01 RESULTS OBSERVED
Authority target: SYNTHETIC SELF-FALSIFICATION SAFETY/SELECTION PRIMITIVE ONLY

## Parent boundary

Parents are `COG-COUNTERMODEL-01R`, `COG-EPISTEMIC-01R`, `COG-MEMORY-01`,
`COG-PLAN-01`, and `COG-INFO-02`. They establish synthetic/narrowed primitives for
surviving countermodels, typed authority, dependency-aware memory, proof-carrying plans,
and decision-relevant information allocation. They do not establish semantic causal
truth, autonomous scientific discovery, production control, large-model transfer, or
external replication.

`CAB-01-Q1-R1` separately qualifies a synthetic causal-authority benchmark harness. It is
not a parent scientific result and cannot be used as evidence that COG-SELF-01 works.

## Question

Can a runtime governor select the lowest necessary-cost *certified* falsification attack
that can alter a live decision, bind that attack to the current proof-carrying plan and
its load-bearing memory/assumption graph, veto irrelevant or stale attacks, and apply
negative outcomes monotonically without ever self-promoting epistemic authority?

## Frozen principle

The governor is not a curiosity engine and is not a causal-truth resolver.

Given a currently admitted world set `M`, a reference candidate world `m0`, and the
predeclared action map `g(m)`, define the action-flipping set

`M_cross = {m in M \\ {m0} : g(m) != g(m0)}`.

An attack is decision-relevant only if:

1. its plan certificate is current and verifies against the current ledger/world set;
2. every declared target memory lies in the transitive dependency closure of a memory
   bound into that plan;
3. every declared target assumption belongs to that same load-bearing memory closure;
4. it explicitly targets every currently action-flipping world it claims to distinguish;
5. its lower-bound rate vector is complete for `M_cross` and carries
   `CERTIFIED_LOWER_BOUND` authority.

Among eligible attacks, selection reuses the frozen COG-INFO-02 decision-relevant
maximin rate-per-cost rule. Therefore maximizing

`min_{m in M_cross} R_{m,q} / c_q`

is equivalent, for the fixed binary-KL information requirement, to minimizing the
information-theoretic necessary cost lower bound among admitted attacks.

If `M_cross` is empty, model uncertainty remains explicit but falsification spend for the
immediate decision is forbidden.

## Frozen negative-update rule

A selected attack may produce one of four bounded runtime outcomes:

- `INCONCLUSIVE` — no authority mutation;
- `SURVIVED` — no authority mutation and specifically no promotion;
- `FALSIFIED_MEMORY` — retract only a memory explicitly targeted by the selected attack;
- `INVALIDATED_ASSUMPTION` — invalidate only an assumption explicitly targeted by the
  selected attack.

Retraction/invalidation may propagate through the existing memory dependency ledger.
No outcome API may mint a stronger `EpistemicRecord`, consolidate new causal memory,
remove a surviving countermodel without a separate typed transition, rewrite a frozen
artifact, or convert test survival into positive causal authority.

The selected decision is digest-bound to the current plan certificate, world digests,
current load-bearing memory digests, candidate world, attack id, and information state.
A stale binding must fail closed before any ledger mutation.

## Frozen runtime states

Selection emits exactly one of:

- `REJECT_INVALID_PLAN_CERTIFICATE`
- `REJECT_NONACTIONABLE_PLAN_STATE`
- `NO_WELL_DEFINED_CANDIDATE_DECISION`
- `NO_DECISION_RELEVANT_ATTACK`
- `NO_LOAD_BEARING_CERTIFIED_ATTACK`
- `NO_CERTIFIED_DECISION_ATTACK`
- `NO_DECISION_IDENTIFYING_ATTACK`
- `ATTACK_CAPACITY_BELOW_NECESSARY_BOUND`
- `INSUFFICIENT_ATTACK_BUDGET`
- `PROPOSE_BOUNDED_FALSIFICATION`

No state denotes causal truth or sufficient evidence.

## Frozen confirmatory cohorts

- PRIMARY seed namespace: `710811..710938`
- REPLICATION seed namespace: `810811..810938`
- `n=128` cases/family/cohort
- `alpha=0.01`
- `target_power=0.95`
- robust action margin `0.05`
- no threshold/state/family repair after observing COG-SELF-01 confirmatory output.

## Frozen families

`S0 ROBUST_DECISION_NO_SPEND`: all represented worlds retain causal/model differences but
recommend the same margin-separated action. Even a cheap high-rate probe is present.
Expected: `NO_DECISION_RELEVANT_ATTACK`, zero spend.

`S1 CHEAP_DECISIVE_ATTACK`: worlds disagree on action; two certified load-bearing attacks
are feasible. Expected: choose the attack with the lower necessary cost bound.

`S2 SAME_DECISION_INFORMATION_TRAP`: one attack is highly informative about a same-action
world but weak against the action-flipping world; another is better on the cross-decision
quotient. Expected: choose the latter.

`S3 CROSS_DECISION_ZERO_RATE`: every eligible attack has zero certified rate against at
least one action-flipping world. Expected: `NO_DECISION_IDENTIFYING_ATTACK` and zero
ledger mutation.

`S4 STALE_PLAN_BINDING`: create a valid plan, then retract a bound memory before selection.
Expected: `REJECT_INVALID_PLAN_CERTIFICATE`, zero spend/mutation beyond the deliberate
pre-attack retraction.

`S5 IRRELEVANT_MEMORY_TARGET`: an attractive attack targets a memory outside the
transitive dependency closure of the plan; a weaker load-bearing attack exists.
Expected: irrelevant attack ineligible and load-bearing attack selected.

`S6 LOAD_BEARING_PARENT_TARGET`: the plan binds a child memory whose active parent is a
transitive dependency. The decisive attack targets that parent. Expected: attack remains
eligible; a `FALSIFIED_MEMORY` outcome retracts parent and dependent child transitively.

`S7 UNCERTIFIED_RATE_TRAP`: an uncertified attack has arbitrarily favorable nominal
rates/cost; a certified weaker attack is feasible. Expected: uncertified attack cannot be
selected.

`S8 BUDGET_OR_CAPACITY_VETO`: alternate cases freeze either inadequate max units or
budget below the necessary KL converse. Expected: exact capacity/budget veto and no
mutation.

`S9 ORDER_INVARIANCE`: permuting attack order, world order, and declared target order
must not change state, chosen attack, necessary-cost bound, or decision digest.

`S10 NEGATIVE_UPDATE_MONOTONICITY`: selected attacks receive either `SURVIVED`,
`FALSIFIED_MEMORY`, or `INVALIDATED_ASSUMPTION`. Survival cannot strengthen authority;
negative outcomes can only retract/invalidate the explicitly bound target and dependency
closure. Memory invariants/event chain must remain valid.

`S11 STALE_OR_UNBOUND_OUTCOME_ATTACK`: after selection, mutate a load-bearing ledger
binding or submit an outcome for a non-target memory/assumption. Expected: outcome
application fails closed with zero additional mutation.

## Frozen primary endpoints

For each cohort independently:

1. every S0-S11 case returns its frozen state/action/outcome behavior in 128/128 cases;
2. S0 false-spend rate = 0;
3. S1/S2/S5/S6/S7 selected-attack correctness = 1.0;
4. S3 false-spend rate = 0;
5. S4 stale-certificate acceptance rate = 0;
6. S5 irrelevant-memory attack selection rate = 0;
7. S8 false-spend rate = 0 and capacity/budget state classification = 1.0;
8. S9 permutation disagreement count = 0;
9. S10 survival-promotion count = 0 and negative-update target violation count = 0;
10. S10 transitive retraction/invalidation propagation rate = 1.0 when a dependency is
    deliberately targeted;
11. S11 stale/unbound outcome acceptance rate = 0;
12. runtime errors = 0;
13. result schema contains no field that can be interpreted as `true_causal_model`,
    autonomous authority promotion, or evidence rewriting permission.

Any endpoint failure => non-passing COG-SELF-01 verdict. A harness defect requires a new
experiment id and fresh seed namespace; the parent result remains immutable.

## Mutation gate

The semantic gate must kill mutations that independently:

- allow S0 spend;
- accept a stale plan;
- select an irrelevant-memory attack;
- select an uncertified attack;
- turn `SURVIVED` into an authority promotion;
- permit an unbound negative-update target;
- permit a stale selected-decision digest;
- flip any prohibited non-promotion boundary flag.

## Non-promotion boundary

Even a PASS qualifies only a synthetic runtime self-falsification selection and
monotone-negative-update primitive. It does not prove:

- that the represented world set is complete;
- that certified information rates are correct in real systems;
- that utilities/action maps are correct;
- autonomous scientific discovery or causal truth;
- real-model or natural-language transfer;
- active production control safety;
- matched-compute architectural advantage;
- external independent replication;
- novelty.

Novelty status is frozen as `UNKNOWN_OVERLAP_CONCEDED` pending explicit literature and
public benchmark comparison.
