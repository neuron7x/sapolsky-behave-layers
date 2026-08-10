# CSCA-07 — Final Verification Record

**Date:** 2026-08-10

## Authoritative scientific boundary

Verdict: `PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_QUALIFIED`.

Qualified:
- passive factual-trace rejection of a declared observable transition law using an anytime-valid e-process;
- exact observational-equivalence impossibility boundary;
- Jacobian-spectrum insufficiency counterexample;
- stable hidden replay-attractor insufficiency counterexample;
- within-model fiber-entropy insufficiency counterexample;
- necessary information/sample-cost converse.

Not qualified:
- true causal abstraction from passive traces;
- semantic causality;
- broad shadow causal authority;
- replay control;
- active causal control.

## Authoritative confirmatory numbers

PRIMARY / REPLICATION, 128 fresh traces per family per cohort, 256 transitions each:

- N0 true observed law: `1/128` / `1/128` rejected (`0.0078125` each; frozen max `.02`).
- S1 wrong dynamics: `128/128` / `128/128` rejected.
- S2 wrong sign: `128/128` / `128/128` rejected.
- W1 weak misspecification: `6/128` / `14/128` rejected; no power requirement because exact rate `.0056 nat/transition` implies necessary `745.8748` transitions for `.95` target power at alpha `.01`, above the frozen budget `256`.

Information requirement: `kl(.95||.01)=4.176898950135489 nat`.

## Exact counterexamples

Spectral/topology:
- adjacency A `[[1,1],[0,1]]`;
- adjacency B `[[1,1],[1,1]]`;
- spectral distance `5.551115123125783e-17`;
- max observable path error `4.440892098500626e-16`.

Hidden replay attractor:
- fixed point `0.8087881752970774`;
- local spectral radius `0.13834467499984965`;
- context derivative `0`;
- observational information about hidden state `0` by construction.

Fiber ambiguity:
- `H(Z|X,M)=0` for each candidate;
- cross-model `H(Z|X)=1 bit`;
- `I(M;X)=0`.

## Post-confirmatory diagnostic

4096 new traces/family; explicitly no claim upgrade:
- N0 rejection `19/4096 = 0.004638671875`;
- W1 rejection `216/4096 = 0.052734375` at 256 transitions.

## Verification

PASS:
- `scripts/csca07_gate.py --self-test`: 4/4 semantic authority mutations killed.
- `scripts/csca07_gate.py`.
- CSCA-06C / 06B / information / 06A-R1 / 06A gates.
- CSCA-05 / CSCA-04 / CSCA-03R gates (CSCA-03R semantic gate without its long self-test in the final aggregate pass).
- RD03, research-ops, research-execution, research-ingestion, causal-debt, VIA, architecture, hermeticity, complexity, inference-integrity, technical-quality, truth, documentation, verdict-binding, evidence-validation.
- `make -f Makefile.cwc verify-evidence`: every checksum-bearing evidence bundle passed, including both CSCA-07 bundles.
- CSCA-07 focused tests: `7 passed`.
- focused CSCA-07 + replay/uncertainty test set: `11 passed`.
- full repository collection: `414 tests collected`, zero collection errors.
- new Python modules/scripts compile with `py_compile`.
- `git diff --check` PASS.

Not claimed:
- the selected 81-test research/VIA suite was attempted but exceeded the 300-second execution window before pytest emitted a final summary; no suite PASS is claimed.
- full behavioral repository pytest PASS is therefore not claimed in this record.

## Final epistemic decision

Passive replay is now fail-closed at the correct information boundary:

`predictive contradiction -> reject model law`

`predictive survival + no identifying assumptions -> causal authority blocked`

`causal candidate -> only under explicit separately tested identifying assumptions`.

The next experiment must add an actual identifying information channel or a falsifiable structural assumption. More replay compute alone is not an admissible next step.
