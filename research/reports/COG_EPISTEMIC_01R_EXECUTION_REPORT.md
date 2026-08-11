# COG-EPISTEMIC-01R — Execution Report

Date: 2026-08-11
Verdict: `TYPED_EPISTEMIC_LATTICE_QUALIFIED_SYNTHETIC_NARROWED`
Authority: `EPISTEMIC_RUNTIME_SAFETY_PRIMITIVE_ONLY`

## Parent failure preserved

The first `COG-EPISTEMIC-01` run remains non-passing. Its sole F11 replication failure was a harness-precondition defect: one nominal upstream draw returned `IDENTIFYING_ASSUMPTION_VIOLATED`, so the target countermodel adapter path was never exercised. The raw result and transition matrix remain checksummed and are not reclassified as a pass.

R1 froze a fresh protocol before execution and changed only the F10/F11 precondition construction to immutable legacy API-state fixtures. No acceptance threshold or family semantics was weakened.

## Implemented runtime primitive

`cwc/epistemics/lattice.py` adds:

- immutable `EpistemicRecord` objects that cannot be directly constructed through the public constructor;
- immutable `EpistemicCapability` tokens minted only by `EpistemicMachine`;
- SHA-256-addressed `EvidenceRef` objects with explicit evidence kind/source/context;
- exact claim, parent-digest and context binding;
- positive chain `OBSERVED -> PREDICTIVE -> ASSUMPTION_CONDITIONAL -> INTERVENTION_SUPPORTED`;
- absorbing `UNIDENTIFIED/FALSIFIED/OOD/ABSTAIN` states;
- direct-intervention source restrictions excluding surrogate/replay evidence;
- deterministic canonical record/capability digests.

`cwc/epistemics/legacy_adapter.py` maps frozen CSCA-08 and COG-COUNTERMODEL-01R string states into the new typed layer without editing historical artifacts.

## Confirmatory matrix

Both PRIMARY and independent REPLICATION used 128 independently bound cases per adversarial family.

Frozen forbidden families:

- F0 direct construction bypass;
- F1 wrong capability class;
- F2 UNIDENTIFIED resurrection;
- F3 FALSIFIED resurrection;
- F4 assumption evidence substituted for direct intervention;
- F5 surrogate mislabeled as direct intervention;
- F6 cross-claim token replay;
- F7 stale-parent token replay;
- F8 scope escalation;
- F9 evidence-hash/evidence-class mutation;
- F10 legacy assumption violation promoted positively;
- F11 surviving legacy countermodel collapsed into positive causal authority.

## Result

PRIMARY:

- legal chain acceptance: `128/128 = 1.0`;
- forbidden promotion acceptances across all 12 families: `0/1536`;
- unexpected/harness errors: `0`.

REPLICATION:

- legal chain acceptance: `128/128 = 1.0`;
- forbidden promotion acceptances across all 12 families: `0/1536`;
- unexpected/harness errors: `0`.

Canonical digest checks passed in both cohorts: identical canonical content produced identical digest; authority-bearing payload change changed digest.

Gate self-test killed `6/6` frozen authority/repair mutations.

## Scientific interpretation

Supported narrowly: CWC now has an executable fail-closed epistemic runtime boundary. Stronger authority cannot be obtained through the supported API without the evidence class, claim binding, parent digest, and scope required by the exact transition.

Not supported: semantic causal truth, real-trace identification, replay utility/control, active control, large-model transfer, architecture Pareto advantage, malicious-host unforgeability, or independent external replication.
