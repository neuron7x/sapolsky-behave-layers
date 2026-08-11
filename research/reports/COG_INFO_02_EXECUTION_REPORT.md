# COG-INFO-02 — Decision-Relevant Information Governor

**Date:** 2026-08-11  
**Preregistration commit:** `87dbd88ae9f8cc72c15db6128d08a9fa25464e59`  
**Implementation commit before confirmatory execution:** `3283c09`  
**Verdict:** `DECISION_RELEVANT_INFORMATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `DECISION_INFORMATION_ALLOCATION_PRIMITIVE_ONLY`

## Result

The current `COG-INFO-01` maximin governor is conservative for *model identification*:
it requires a positive certified rate against every unresolved alternative. `COG-INFO-02`
adds a separate decision-identification governor that first quotients the model set by
the predeclared immediate decision `g(m)=argmax_a U(a,m)` and computes the information
bottleneck only over alternatives that change that decision.

This does **not** delete same-decision countermodels. They remain unresolved epistemic
debt and still block causal-model truth. They simply cannot force extra acquisition when
the declared question is only the immediate action choice.

## Confirmatory design

PRIMARY seed namespace `104201..` and independent internal REPLICATION namespace
`204201..`; 12 frozen families; 128 cases/family/cohort; alpha `0.01`, target power
`0.95`. No threshold repair was permitted.

All 12 families passed `128/128` independently in PRIMARY and REPLICATION.

Load-bearing cases:

- `D0`: all surviving causal models recommend the same action -> zero acquisition in
  `256/256` pooled cases despite unresolved model identity.
- `D1`: a same-decision countermodel has exactly zero information rate while the
  action-flipping countermodel has a positive rate. Legacy model-maximin returns
  `NO_IDENTIFYING_INFORMATION_CHANNEL` in `256/256`; decision-relevant governor licenses
  the decisive probe in `256/256`. Median necessary decision-information cost was
  `18.6560` cost units.
- `D2`: a cross-decision alternative has zero certified rate -> zero false spend.
- `D4`: high nuisance information about same-decision worlds never beats the probe with
  stronger cross-decision information.
- `D5/D6`: capacity and budget vetoes remain distinct and fail closed.
- `D8/D9`: uncertified and incomplete rate vectors cannot authorize spend.
- `D10`: zero permutation disagreements.
- `D11`: when both governors can spend, removing a same-decision bottleneck reduced the
  necessary-cost lower bound in `256/256` cases. Legacy/decision cost ratio median
  `9.7754x`, range `6.2539x..17.0071x` on the frozen family.

## Interpretation

The result establishes a synthetic separation:

`causal-model identification != decision identification`.

A system may be unable to identify which causal world is true yet still have an
identified action if every surviving world recommends the same action. Conversely, if
surviving worlds recommend different actions, only evidence that distinguishes those
decision cells can resolve the immediate decision.

The existing binary-KL formula remains a **necessary converse only**. A permitted spend
is not a sufficient test guarantee and is not causal authority.

## Related-work / novelty boundary

No novelty claim is made. The result overlaps with classical value-of-information,
decision-focused learning, robust/imprecise decision making, active causal discovery,
recent decision-sufficient representations, Active Epistemic Control, and uncertainty-
aware causal decision making. The candidate CWC contribution is narrower: executable
composition of surviving causal countermodels, decision-quotient filtering, certified
information lower bounds, KL compute vetoes, typed epistemic authority, memory and
proof-carrying planning. Whether that systems composition is novel or useful outside the
synthetic harness remains UNKNOWN.

## Non-promotion boundary

Still unqualified: semantic causal truth, real-world planning value, active control,
large-model transfer, production/Pareto advantage, and external third-party replication.
