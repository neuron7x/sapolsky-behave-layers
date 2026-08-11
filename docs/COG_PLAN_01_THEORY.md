# COG-PLAN-01 — Proof-Carrying Counterfactual Planning Theory

## Core decision object

The planner does not ask which world model is most plausible and then act as if that
world were true. It receives the **entire admitted world set** and asks whether the
same action is uniquely preferred in every member of that set.

For worlds `m in E`, actions `a in A`, utilities `U_m(a)` and frozen margin `delta`,
a robust action exists only if there is one `a*` such that

`U_m(a*) - max_{a != a*} U_m(a) >= delta`

for every admitted world `m`.

This is decision identification under model ambiguity. It is strictly weaker than
identifying the true causal world: different worlds may remain unresolved while still
implying the same action.

## Why world averaging is forbidden

A prior-weighted or arithmetic mean can prefer action A even when an admitted world
strongly prefers B. Such an average silently converts unresolved model uncertainty
into action authority. `COG-PLAN-01` therefore exposes no world-prior parameter in the
robust-action path. A world reversal forces abstention or information acquisition.

## Countermodel-complete planning

A quarantined `INTERVENTION_SUPPORTED` memory that retains countermodels can participate
in robust decision analysis only when every surviving countermodel id is explicitly
represented in the admitted world set. Missing a surviving countermodel blocks the
plan rather than silently narrowing uncertainty.

## Assumption-conditional planning

If a required memory is `ASSUMPTION_CONDITIONAL`, a common robust action may be
represented as an `ASSUMPTION_CONDITIONAL_PLAN`, never as unconditional robust
authority. The assumption remains part of the proof obligation.

## Information acquisition fallback

When worlds disagree, the planner may request evidence only through the existing
certified maximin information-per-cost governor. For target power `p` at level `alpha`,
the binary-KL converse requires at least `kl(p||alpha)` nats. An information action is
eligible only when certified lower-bound rates cover every unresolved alternative and
the available budget is not below the resulting necessary cost bound.

This remains a necessary spend permission, not a sufficient correctness guarantee.

## Proof-carrying certificate

Every result binds by SHA-256:

- plan id and context scope;
- current memory ids + exact memory digests;
- every admitted world id + exact world/utility digest;
- decision state and selected action;
- robust margin;
- information decision/action and necessary cost when applicable.

Memory revision/retraction, world removal/replacement, utility mutation or context
change invalidates the old certificate.

## Boundary

This primitive can establish that the **decision rule** preserved set-valued
uncertainty on the frozen synthetic families. It cannot establish that the world set is
complete in nature, that utilities are correct, that causal semantics are true, or that
the resulting planner improves real tasks. Those require separate gates.
