# COG-EPISTEMIC-01 — Initial Confirmatory Execution (Frozen Negative)

Verdict: `TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED` for the original frozen harness.

The implementation itself blocked every exercised illegal transition, but the frozen F11 legacy-integration family was incorrectly specified as requiring the upstream stochastic CSCA-08 regime evaluator to return `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS` on every one of 128 seeds. In REPLICATION case 42 the upstream evaluator legitimately returned `IDENTIFYING_ASSUMPTION_VIOLATED`. The harness counted that non-promotion as a harness error and therefore failed its own zero-error endpoint.

This result is preserved. It is not reinterpreted as a positive. The defect is in the composition benchmark: it conflated an upstream scientific state with the downstream property being tested (whether a surviving countermodel can be silently promoted). `COG-EPISTEMIC-01R` will isolate that downstream property using a prospectively frozen direct construction of an assumption-conditional upstream record and fresh cohort namespaces.
