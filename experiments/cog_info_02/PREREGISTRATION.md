# COG-INFO-02 — Decision-Relevant Information Governor

Date frozen: 2026-08-11
Status: PREREGISTERED / NO CONFIRMATORY RESULTS OBSERVED

## Parent boundary

Parents are `COG-COUNTERMODEL-01R`, `COG-EPISTEMIC-01R`, `COG-MEMORY-01`, and
`COG-PLAN-01`. They establish only synthetic/narrowed safety primitives. None grants
semantic causal truth, active control, large-model transfer, or external replication.

`COG-INFO-01` currently chooses evidence by maximin certified information-per-cost over
*all* unresolved model alternatives. This is appropriate for model identification, but
can be unnecessarily conservative for a downstream decision: an observationally
indistinguishable alternative that recommends the same action can become the maximin
bottleneck even though resolving it has zero value for the current action choice.

## Question

Can the information governor spend compute only on distinctions that can change the
current robust decision, while remaining fail-closed under unresolved cross-decision
alternatives, zero identifying rate, uncertified rates, capacity limits, and insufficient
budget?

## Formal object

Let `M(D)` be the surviving model set and let

`g(m) = argmax_a U(a,m)`

be the predeclared decision class induced by model `m` (ties are outside this first
kernel). The decision partition is the quotient `M(D)/~_g`, where `m ~_g m'` iff
`g(m)=g(m')`.

For a reference candidate with decision `g0`, only alternatives

`M_cross = {m : g(m) != g0}`

are decision-relevant falsifiers for the immediate action. Given a certified lower
bound `R_{m,q}` (nats/acquisition-unit) and unit cost `c_q`, define

`Q_dec(q) = min_{m in M_cross} R_{m,q} / c_q`.

The existing binary-KL converse remains only a necessary condition:

`Cost >= kl(power || alpha) / Q_dec(q)`.

If `M_cross` is empty, the current decision is identified across the admitted model set
without identifying the true causal model. If `M_cross` is nonempty and every admitted
query has zero certified rate for at least one member, the decision is unidentifiable
under the admitted channels and extra compute is vetoed.

## Frozen API states

The new governor must emit exactly one of:

- `DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION`
- `NO_CERTIFIED_DECISION_INFORMATION_RATE`
- `NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL`
- `DECISION_ACTION_CAPACITY_BELOW_NECESSARY_BOUND`
- `INSUFFICIENT_DECISION_INFORMATION_BUDGET`
- `ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE`

No state means semantic causal truth or sufficient evidence.

## Frozen confirmatory cohorts

- PRIMARY seed namespace: `104201..104328`
- REPLICATION seed namespace: `204201..204328`
- `n=128` cases/family/cohort
- `alpha=0.01`
- `target_power=0.95`
- no threshold repair after result observation.

## Frozen families

`D0 ALL_SAME_DECISION`: all surviving models recommend the same action. Expected: no acquisition.

`D1 SAME_DECISION_ZERO_RATE_TRAP`: one same-action alternative has certified rate zero,
while every cross-decision alternative has a positive certified rate and a feasible
budget. Expected: acquire. The legacy model-identification maximin is expected to be
blocked; this is the load-bearing strict-separation family.

`D2 CROSS_DECISION_ZERO_RATE`: at least one cross-decision alternative has zero rate
under every certified action. Expected: no identifying decision channel.

`D3 COST_TRADEOFF`: multiple complete certified probes; choose the one maximizing
cross-decision min-rate / cost, not raw rate.

`D4 NUISANCE_INFORMATION_TRAP`: a probe is highly informative only about same-decision
worlds while another is weaker globally but stronger on cross-decision worlds. Expected:
choose the latter.

`D5 ACTION_CAPACITY_VETO`: best decision-relevant action cannot physically supply enough
units to reach the necessary information converse. Expected: capacity veto.

`D6 BUDGET_VETO`: channel capacity is adequate but the available budget is below the
necessary converse. Expected: budget veto.

`D7 MULTI_CROSS_DECISION_MAXIMIN`: two or more cross-decision alternatives; one is the
bottleneck. Expected: action chosen by the true cross-decision maximin score.

`D8 UNCERTIFIED_RATE_TRAP`: an uncertified action has arbitrarily attractive rates but a
weaker certified action exists. Expected: uncertified action cannot authorize spend.

`D9 PARTIAL_RATE_VECTOR`: action omits a cross-decision alternative. Expected: it is
ineligible, even if its present rates are high.

`D10 ORDER_INVARIANCE`: permutation of action and model ordering cannot change output.

`D11 STRICT_COST_IMPROVEMENT`: both legacy and decision-relevant governors can spend,
but a same-decision bottleneck makes the legacy necessary-cost lower bound strictly
larger. Expected: decision-relevant bound is strictly smaller while preserving the
same alpha/power target.

## Primary endpoints

For each cohort independently:

1. every family returns the frozen state/action behavior in 128/128 cases;
2. D0 false-spend rate = 0;
3. D1 feasible decision-relevant spend rate = 1.0 and legacy rescue rate = 1.0;
4. D2 false-spend rate = 0;
5. D3/D4/D7 selected-action correctness = 1.0;
6. D5/D6 false-spend rate = 0;
7. D8 uncertified-action selection rate = 0;
8. D9 incomplete-vector selection rate = 0;
9. D10 permutation disagreement count = 0;
10. D11 strict necessary-cost improvement rate = 1.0;
11. no result object contains a `true_causal_model` or equivalent authority field;
12. runtime errors = 0.

Any endpoint failure => non-passing confirmatory verdict. A harness defect requires a
new experiment id and fresh seed namespace.

## Non-promotion boundary

Even a PASS qualifies only a synthetic decision-relevant information-allocation
primitive. It does not prove novelty, semantic causal truth, real-world planning value,
active-control safety, large-model transfer, compute Pareto superiority, or external
replication.

## Related-work overlap frozen before confirmatory execution

This idea overlaps substantially with classical value-of-information/test selection,
decision-focused learning, robust/imprecise decision making, active causal discovery,
and recent epistemic planning. The specific contribution under test is therefore not
"decision-relevant information" as a new concept. The narrow candidate contribution is
an executable fail-closed composition of: surviving causal-model equivalence classes,
decision-quotient filtering, certified information-rate lower bounds, a KL necessary-cost
veto, and proof-carrying epistemic authority. Novelty remains UNKNOWN pending a formal
literature review and external evaluation.
