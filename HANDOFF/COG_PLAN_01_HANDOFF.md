# COG-PLAN-01 HANDOFF

## Result

`PROOF_CARRYING_COUNTERFACTUAL_PLANNER_QUALIFIED_SYNTHETIC_NARROWED`

Authority: `PLANNING_SAFETY_PRIMITIVE_ONLY`.

## New cognitive path

`typed epistemic record -> assumption-aware memory -> admitted countermodel set -> robust action test -> certified information request or abstention -> SHA-bound plan certificate`

## Critical invariants

- no world averaging may create `ROBUST_ACTION`;
- every surviving countermodel must be represented when it is memory debt;
- assumption-conditional memory can yield only a conditional plan;
- stale memory or altered world sets invalidate old certificates;
- information spending requires a certified lower-bound information channel and a
  budget that is not already ruled out by the necessary KL converse;
- no field representing `TRUE_CAUSAL_MODEL` exists in the plan certificate.

## Confirmatory evidence

PRIMARY + REPLICATION: 12 families x 128 cases each, all pass. Hidden-averaging,
stale-memory, dropped-world, zero-information and legacy/retracted attacks all fail
closed. Gate mutations: 7/7 killed.

## Next hard gate

`COG-SELF-01 — Autonomous Falsification Governor`.

The next primitive should choose the weakest load-bearing claim/memory/plan dependency,
generate or retrieve the cheapest surviving countermodel attack, ask the information
governor whether any admissible evidence can reduce the equivalence class, and spend
compute only when the expected/certified epistemic value can change a decision. It
must not self-grant scientific authority or rewrite frozen evidence.
