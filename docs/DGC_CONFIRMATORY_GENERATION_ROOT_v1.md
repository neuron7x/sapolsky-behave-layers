# DGC Confirmatory Generation Root v1

Date: 2026-08-23
Status: `ENGINEERING_AUTHORITY_CONTRACT / EXTERNAL EXECUTION PENDING`

## Problem

DGC already had strong individual controls for source authority, workload materialization, evaluation harness equality, B0-B3 baseline freezing, cluster-aware trial sizing, distributed work coordination and result certification. The remaining integration risk was **cross-layer evidence drift**: each component could be valid by itself while a real confirmatory run accidentally combined objects from different evidence generations.

Examples of invalid combinations include:

- materialized workload A with task manifest B;
- B2 fitted under one calibration population but attached to another baseline panel;
- a new statistical plan with an old repeated-trial count;
- a distributed run whose task or policy population differs from the frozen harness;
- a result population committed under a different distributed spec;
- code executed from a different repository commit/tree than the one frozen before outcomes.

## Root contract

`cwc/governance/confirmatory_generation.py` creates one immutable `ConfirmatoryGenerationRoot` before confirmatory execution.

The root binds:

1. evidence generation ID;
2. external workload family;
3. exact repository commit object ID;
4. exact repository tree object ID;
5. `MATERIALIZED_VERIFIED` source-authority digest;
6. materialized workload tree SHA-256;
7. materialized task-manifest SHA-256;
8. one controlled-comparison frame digest;
9. executable-frozen B0-B3 baseline-panel digest;
10. frozen product statistical-plan digest;
11. cluster-aware repeated-trial sizing digest;
12. distributed-evaluation spec digest;
13. exact policy-id -> governance-policy -> full-harness bindings;
14. exact expected work-unit count.

The root digest is a canonical SHA-256 over those identities.

## Hard invariants

A confirmatory generation cannot freeze unless all of the following hold:

- source authority is exactly `MATERIALIZED_VERIFIED`;
- source task manifest equals the distributed task population manifest;
- B0-B3 panel is `executable_frozen=true`;
- distributed replicate count equals the cluster-aware required trials/task;
- trial-sizing alpha and target power equal the frozen statistical plan;
- policy-harness IDs exactly equal the distributed policy population;
- every policy arm uses the same controlled-comparison frame;
- every policy arm has a distinct governance-policy digest;
- every harness binds the same materialized task manifest, statistical plan and baseline panel;
- distributed spec binds the same comparison frame and statistical plan;
- repository commit/tree IDs are explicit Git object IDs.

## Completion authority

`certify_confirmatory_completion` accepts a distributed completion certificate only if:

- its distributed-spec digest equals the frozen generation root;
- `complete=true`;
- expected and committed units both equal the full frozen work population;
- result-population digest and audit-root digest are SHA-256 identities;
- total cost is finite and non-negative.

It then emits a separate `execution_population_digest` binding the generation root to the completed evidence population.

## Falsification

Targeted local tests: `8/8 PASS`.

`tests/test_dgc_confirmatory_generation.py` attacks:

- source-stage substitution;
- task-population drift;
- non-frozen B2/B0-B3 panel;
- repeated-trial count drift;
- comparison-frame drift;
- distributed-spec/harness drift;
- foreign completion certificate;
- partial completion.

`scripts/dgc_confirmatory_generation_attack.py` is the canonical cross-layer adversarial gate.

## Claim boundary

This contract proves only that a future confirmatory execution can be **cryptographically and semantically bound to one frozen evidence generation** under the declared schemas.

It does **not** prove:

- that the external benchmarks have been materialized in the current environment;
- that B2 has been fitted on external calibration data;
- that model/provider trials have run;
- quality noninferiority or cost superiority;
- generalization;
- production safety;
- frontier-scale distributed operation.

`PRODUCT_QUALIFIED` therefore remains false until the external evidence chain is actually observed.
