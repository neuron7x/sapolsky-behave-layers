# CNEH-EXP-03C — exact directed isolation falsifier

Prospective simulator verification; no cognitive efficacy claim. Parent EXP03B implementation and first observed evidence: 0429a8c3a11f2b34e51ea217c96648b7cf699457, CI 45257366009. Preserve all previous protocols and results. This protocol is frozen before running the new cohort.

## Conditional invariant

On the pinned BN-Syn reference backend, B's next membrane voltage, adaptation, spike bits and AMPA/NMDA/GABAA conductances are functions only of its current local physical state, incoming weights times prior spikes, exogenous input, applied scalar gain and direct injected current. With all A-to-B E/I weights exactly zero, identical B-to-B weights, common applied gain, common B external current and matching exogenous tape, identical B state at the intervention tick implies identical B state thereafter by induction. Global gain estimator state may differ; only its actual applied scalar is clamped. Residual conductances from before the intervention are retained, not reset. This invariant is specific to these source semantics, not a proof of isolation in biological brains.

## Frozen design

Eight new public seeds 84001–84008, 32 AdEx neurons, balanced E/I populations identical to EXP03B, 1000 ticks at 0.1 ms, intervention at tick 400. Reuse the exact EXP03B bounded mean-free probe, model parameters and source lock. Paired arms: CUT_CLAMP_BASE, CUT_CLAMP_PROBE_A, CUT_CLAMP_B_POSITIVE_CONTROL. All arms have zero A-to-B incoming weights after tick 400, same common pre-intervention gain clamped before each step, unchanged B-to-B weights. Positive control intentionally injects +20 pA into B from tick 400 onward; it is not a leakage example. It must be detected by the exact local-state comparator. Require the A probe to change A physical state at least once per world; reject a vacuous isolation test. No unregistered input change.

## Acceptance

Compare raw IEEE-754 binary64 bytes, including signed zero, of B voltage, adaptation and three conductance vectors and exact B spike bits at every tick. Record full arrays, not aggregate means or only a digest. Check initial equality, identical pre-intervention histories, common RNG-state digests at every tick, full actual B current buffer, common applied gain, complete directed zero mask and unchanged off-target weights. Verify actual conductance update against independent scalar oracle. Any B-state difference between the isolation pair is MODEL_ISOLATION_FALSIFIED; fail nonzero after preserving counterexample. Positive control must diverge and source A must respond; otherwise INSTRUMENT_UNQUALIFIED. Every seed and trace retained. Fresh full replay plus strict manifest; immutable separate output. No tolerance for B physical-state comparison. This is a finite execution test of the conditional invariant, not universal proof of CNEH. Scientific promotion=false; external replication NOT_TESTED; physical energy INSTRUMENT_INVALID.
