# NPI-01 PRE-EXECUTION AMENDMENT 001 — Nullspace basis validity

Date frozen: 2026-08-12
Status: PRE-EXECUTION HARNESS REPAIR / NO SCIENTIFIC VERDICT OBSERVED

## Trigger

The first implementation self-test returned `HARNESS_INVALID`: mutation attacks 1-5 were killed, but `WRONG_NULLSPACE_BASIS` was not. The implementation computed the projected action-gradient score using the supplied basis but did not independently verify that the supplied basis actually lies in `ker J`.

No scientific `NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED` verdict was emitted or sealed.

## Frozen repair

Before evaluating the NPI score, the harness must verify the structural predicate

`J n = 0`

for every supplied nullspace basis vector `n`, and must require each basis vector to be nonzero. A certificate with a basis that violates this predicate is invalid and cannot satisfy the counterexample gate.

This amendment does not alter:

- H-NPI-01;
- the counterexample family `Delta_K = 1 - K v^2`;
- the five frozen radii;
- the six mutation attacks;
- the action-reversal kill rule;
- the claim boundary.

The repair only makes mutation 6 executable as originally intended.
