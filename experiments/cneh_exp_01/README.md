# CNEH-EXP-01 — controlled synthetic preflight

**Canonical hypothesis:** CNEH-04-DC. **Status:** FORMALIZED / EMPIRICAL VALIDATION PENDING.

This directory is an executable **toy system**, not a neural simulation, complete CNEH integration, external validation, or evidence for emergent general intelligence.

## Execute

```sh
python -m unittest discover -s tests -p 'test_cneh_exp_01*.py' -v
python experiments/cneh_exp_01/run.py --phase smoke --out /tmp/cneh-smoke
python experiments/cneh_exp_01/run.py --out /tmp/cneh-smoke --verify
python experiments/cneh_exp_01/run.py --phase primary --out /tmp/cneh-primary
python experiments/cneh_exp_01/run.py --out /tmp/cneh-primary --verify
(cd /tmp/cneh-primary && sha256sum -c SHA256SUMS)
```

No `pip` installation is required for the synthetic harness, analytic fixtures,
commitment tooling or tests. The optional neural integration uses a separate locked
environment. A new output directory is required; concurrent writers cannot replace
an existing bundle. Evidence v2 adds `implementation.json`, binds the runner SHA256,
and hashes exact `float.hex()` trajectories. Verification replays every raw row and
checks every derived sidecar field. This uses the same implementation, not an
independent scientific estimator. Historical v1 bundles require the original code
revision; they are not overwritten or silently upgraded.

## Measured versus unmeasured

This pilot records *simulated control-input effort* and deliberately simple *algorithmic operation proxies*, **not real joules, wall-clock hardware latency or FLOPs**. The included static-fusion and scrambled comparisons are diagnostic; the scrambled arm matches bytes/envelopes but its 3-step lag also changes data freshness, so any benefit over it is **confounded** and ineligible for a communication-specific causal conclusion.

The `CENTRAL_EMULATOR` is not handicapped. It receives both physical observations, implements the exact same update as `COUPLED`, and yields identical action/state traces. Any claimed strict advantage over it is invalid under the simulation-dominance boundary.

No external blinded replication has been performed, and local reruns cannot be
described as independent replication. `SUPPORTED_NARROW` is structurally unreachable
in this frozen lineage: its conjunction requires a positive LCB against a trace-identical
emulator. Closing other gates cannot change this logical obstruction. A bounded
comparator claim requires a separate prospective lineage and untouched cohorts.

A pinned BN-Syn adapter now executes real spiking dynamics as **integration smoke
only**. It does not replace the frozen synthetic PRIMARY, establish a neural goal
task, qualify causal attribution, or prove distributed physical cost parity.
Other candidates in the historical source lock remain unintegrated. Historical
references to other owners are preserved; this work uses only `neuron7x` repositories.

## Preregistration discipline

`PREREGISTRATION.md` and `protocol.json` were committed to this branch before any CNEH runner code and before the local synthetic pilot. The first internal 128-seed run is internal synthetic evidence; it cannot qualify a blind independent replication. No existing CWC result or historical negative is modified.

The additive [engineering amendment](INTEGRATION_CONTRACT.md),
[component contract](qualification_contract.json) and
[neural contract](bnsyn_integration_contract.json) were committed before their new
qualification probes. No original threshold, seed, primary contrast or source lock
was changed. [Qualification guide](QUALIFICATION_GUIDE.md) documents commands,
acceptance evidence and remaining external gates.
