# CNEH-EXP-01 — controlled synthetic preflight

**Canonical hypothesis:** CNEH-04-DC. **Status:** FORMALIZED / EMPIRICAL VALIDATION PENDING.

This directory is an executable **toy system**, not a neural simulation, complete CNEH integration, external validation, or evidence for emergent general intelligence.

## Execute

```sh
python -m unittest discover -s tests -p test_cneh_exp_01.py -v
python experiments/cneh_exp_01/run.py --phase smoke --out /tmp/cneh-smoke
python experiments/cneh_exp_01/run.py --out /tmp/cneh-smoke --verify
python experiments/cneh_exp_01/run.py --phase primary --out /tmp/cneh-primary
python experiments/cneh_exp_01/run.py --out /tmp/cneh-primary --verify
sha256sum -c /tmp/cneh-primary/SHA256SUMS # run inside bundle folder instead
```

No `pip` installation is required. Each evidence bundle is immutable and contains `SHA256SUMS`, per-arm paired data, frozen protocol/source copies, resource/safety/negative controls and `verdict.json`. Verify with the built-in verifier: it independently recomputes all paired contrasts from the frozen CSV and refuses status promotion.

## Measured versus unmeasured

This pilot records *simulated control-input effort* and deliberately simple *algorithmic operation proxies*, **not real joules, wall-clock hardware latency or FLOPs**. The included static-fusion and scrambled comparisons are diagnostic; the scrambled arm matches bytes/envelopes but its 3-step lag also changes data freshness, so any benefit over it is **confounded** and ineligible for a communication-specific causal conclusion.

The `CENTRAL_EMULATOR` is not handicapped. It receives both physical observations, implements the exact same update as `COUPLED`, and yields identical action/state traces. Any claimed strict advantage over it is invalid under the simulation-dominance boundary.

No external blinded replication has been performed, and local reruns by the same operator cannot be described as independent replication. `SUPPORTED_NARROW` is blocked. Follow-up neural/DNCA/time-rupture/neosynaptex adapters are future work; `frozen_sources.lock` pins candidates only.

## Preregistration discipline

`PREREGISTRATION.md` and `protocol.json` were committed to this branch before any CNEH runner code and before the local synthetic pilot. The first internal 128-seed run is internal synthetic evidence; it cannot qualify a blind independent replication. No existing CWC result or historical negative is modified.
