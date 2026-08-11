# CAB-01-Q1-R1 — Leakage-Null Repair Preregistration

**Status:** FROZEN BEFORE R1 IMPLEMENTATION AND EXECUTION  
**Date:** 2026-08-11  
**Parent Q1 verdict:** `CAB01_Q1_NOT_QUALIFIED`  
**Parent Q1 evidence commit:** `2d3bec65972a213dcdb0f24ef53a4edf4b3f0ec2`  
**Authority:** benchmark qualification retry only

## Reason for R1

Q1 failed only because its held-out surface-only classifier was compared with the
full-cohort majority-class rate. The serialized surface feature vector had exactly one
unique value, so the classifier had no discriminating feature; however the deterministic
held-out fold had a slightly different class prior than the full cohort.

R1 changes only the leakage-null evaluation. It does not change task families, generator
semantics, state precedence, baselines, policy interfaces, query costs/rates, metrics or
Pareto rule.

## Frozen fresh namespaces

- `PRIMARY_R1`: seed base `510811`
- `REPLICATION_R1`: seed base `610811`
- ordinary F0-F10: `128` instances/family/cohort
- F11: `128` mutation groups/cohort, three variants/group
- all other execution constants inherit CAB-01-Q1 unchanged

No Q1 seed is reused.

## R1 leakage gate

Two conjunctive checks are required:

1. **structural surface null:** exactly one unique `surface_signature` exists over the
   full cohort;
2. **held-out predictive null:** the deterministic modulo-5 surface-only classifier is
   compared to the majority-class rate of that same held-out fold:

   `surface_only_accuracy <= heldout_majority_class_rate + 1e-12`.

The full-cohort majority rate is still reported but is not the R1 null reference.

This repair is justified only because Q1 established that the classifier input had one
unique value; R1 must fail if the signature count becomes greater than one, even if
predictive accuracy stays near chance.

## Unchanged qualification conjunction

R1 additionally requires all inherited Q1 gates:

- byte-identical regeneration/replay;
- exact family counts;
- construction == analytic oracle == runtime oracle for every case;
- exact F11 ACT/QUERY/ABSTAIN triads;
- both constant policies Pareto-dominated by at least one non-oracle baseline;
- checksum-bound artifacts;
- mutation/self-test kill gate;
- all non-promotion flags remain false.

## Verdict rule

All gates pass -> `CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC`.
Any one fails -> `CAB01_Q1_R1_NOT_QUALIFIED`.

Even a PASS remains benchmark-internal and cannot establish real-model transfer, CWC
superiority, semantic causality, natural-language contamination resistance, large-model
Pareto advantage or external replication.
