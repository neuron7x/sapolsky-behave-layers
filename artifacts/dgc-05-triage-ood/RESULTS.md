# DGC-05 Software-Triage OOD / Combinatorial Generalization — Results

Known-combination status: **TRIAGE_COMBINATORIAL_OOD_SUPPORTED**.  
Unknown-domain status: **UNKNOWN_DOMAIN_FAIL_CLOSED**.

## Unseen known-fault combinations

The cohort contains `21` non-empty A/H/C/S/I combinations that were absent from DGC-04.

| Policy | Decision accuracy | False passes | Validator calls |
|---|---:|---:|---:|
| B0 FULL | 1.000000 | 0 | 105 |
| B1 PATH ROUTER | 1.000000 | 0 | 61 |
| B2 DGC | 1.000000 | 0 | 21 |

DGC validator-call savings are `0.800000` vs B0 and `0.655738` vs B1, with full task coverage.

## Unknown-domain fail-closed test

`U`, `A+U`, and `I+U` all resolve to `RELEASE_ABSTAIN`; autonomous `RELEASE_PASS` authority is false because no validator authority exists for `U`.

## Boundary

This is OOD/combinatorial evidence only inside the same repository fault family and validator topology. It does not establish model-family, provider, client, or arbitrary software generalization.
