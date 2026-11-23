# CNEH-EXP-03 — prospective structural intervention pilot

**Status:** FORMALIZED / EMPIRICAL VALIDATION PENDING. **Tier:** internal simulator mechanism qualification, not a confirmatory efficacy study.

Parent: merged PR43 and PR44, main at `959c2f089e6a3f143b64429cd4a2e84a778da8e7`. Preserve their frozen protocols, negative results and evidence bytes. This prospective protocol is committed before the new runner and before any EXP03 outcome is observed. No outcome-conditioned change to the eight public seed fixtures, intervention, input, endpoints or controls is allowed.

## Question and causal design

Does an explicitly intervened directed interpopulation synaptic structure modify population B's response to a controlled input to population A in the pinned BN-Syn AdEx simulator? Prior EXP01/02 neural work established interface operation, voltage responses, active spiking in calibration, and faithful emulation, not functional coupling or structural OOD response.

Use a paired 2 x 2 factorial experiment: SHAM vs deletion of A-to-B excitatory AND inhibitory edges, crossed with baseline input vs a fixed harmonic input to A. Each world seed defines identical initial state, network topology and exogenous random tape in all four arms. At tick 400 replace both connectivity containers in every arm. SHAM uses exact copies; CUT changes only A-source/B-target weights to zero, with all other entries unchanged. Preserve conductances, adaptation, state, RNG and the global criticality controller. The input to B is held identical. The structural intervention is separate from the additive current probe. Neither replaces the other.

The two populations each contain 12 excitatory and four inhibitory neurons. Dense matrices are postsynaptic rows, presynaptic columns, with distinct E/I index spaces. Validate this mapping and the exact cut mask; reject a topology without any A-to-B edge rather than invent one.

## Frozen outcomes and limits

Primary descriptive endpoint: total post-intervention B spikes / number of B neurons. Compute within-world factorial interaction I_B = (Y_sham,probe - Y_sham,base) - (Y_cut,probe - Y_cut,base). Secondary: analogous interaction of mean post-window B membrane voltage. Report every signed per-world contrast and the mean. No p-value, CI threshold, efficacy or population-generalization claim is licensed by this small engineering cohort. Preserve all zero or contrary interactions. If a fixture has no pre-intervention spikes in either population, report the regime unqualified rather than dropping the seed.

Exact pre-intervention histories, RNG state digests, identical direct B inputs and exact structural intervention masks are validity conditions. A state-only response difference is diagnostic, not a required favorable outcome. A matched SHAM must not change weights. Global criticality feedback and alternative recurrent paths remain active; the interaction measures **total simulator response modification under the specified intervention**, not unique direct synaptic mediation or PID.

## Provenance and resources

Use PR43's authenticated BN-Syn source scope and hash-locked runtime; reference backend, deterministic seeded environment, single-thread BLAS. Record actual source digest and contracts, exact binary64 state digests, spike counts, inputs and structure witnesses. Verify fresh output by complete deterministic replay and strict artifact roster/manifest. Same-environment exact replay is not a cross-platform determinism promise. Fixed input sequences are a system-identification probe, not an optimal dual controller. No physical energy, transport, FLOP equivalence or neural goal efficacy claim.

All endpoints are simulator-level engineering diagnostics. `scientific_promotion_authorized=false`, `REPLICATION_NOT_TESTED`, and physical energy `INSTRUMENT_INVALID` are invariant. A later confirmatory neural task and restricted comparator require a distinct frozen protocol and untouched seeds.
