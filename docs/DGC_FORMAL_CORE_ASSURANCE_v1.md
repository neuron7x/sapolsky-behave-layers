# DGC Formal Core Assurance v1

Status: `FORMAL_GATE_PRESENT / EXECUTION_AUTHORITY_PENDING`

## Scope

Formal methods are applied only where DGC has crisp symbolic safety invariants. This document does **not** claim formal verification of the LLM, the entire DGC runtime, real-world performance, causal assumptions, statistical exchangeability, provider behavior or deployment safety.

The formal gate is `scripts/dgc_formal_core_gate.py`, executed with pinned `z3-solver==5.0.0.0` from `dgc-formal-requirements.txt`.

## SMT obligations

### F1 — reservation budget safety

If the current invariant is

`spent + reserved <= global_budget`

and a new reservation satisfies

`new_reservation <= global_budget - spent - reserved`,

then dispatch preserves

`spent + reserved + new_reservation <= global_budget`.

### F2 — commit budget safety

If an active reservation `released` covers actual cost `actual`, and `released <= reserved`, then replacing the reservation by the actual spend cannot increase `spent + reserved` beyond the existing global budget bound.

### F3 — expiry budget safety

Releasing a non-negative expired reservation cannot violate the global budget invariant.

### F4 — robust VOC admission implication

For the declared additive robust lower bound

`robust_lower = gain_lower - cost - ambiguity_penalty - 2*eta - kappa`,

`robust_lower > 0` implies nominal lower gain exceeds the complete declared penalty stack.

### F5 — Pareto authority conjunction

A formal authorization predicate requiring positive cost-gain LCB plus quality/regret non-inferiority cannot be true while any of those declared lower-bound conditions is false.

## Why this is narrow

These are symbolic control-plane properties. The solver cannot prove that:

- the input evidence is truthful;
- statistical assumptions hold on a client distribution;
- ambiguity radii or causal graphs are correct;
- a model will generalize;
- provider costs/latencies match forecasts;
- production monitoring catches all failures.

Those remain empirical, statistical or external-authority obligations.

## Assurance position

NIST guidance treats formal methods as valuable but insufficient: proofs cover formalized assumptions and components, while testing and post-deployment assurance remain necessary. DGC therefore combines formal core obligations with executable falsification, exact finite model checks, external workload protocols and continuous monitoring gates.

## Current verdict

The formal solver gate is integrated into `dgc-math.yml`. Until a runner actually installs Z3 and returns all five obligations as UNSAT under negation, report:

`FORMAL_CORE_EXECUTION = UNKNOWN`

not `PASS`.
