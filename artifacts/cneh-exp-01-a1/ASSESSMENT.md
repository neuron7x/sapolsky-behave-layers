# CNEH-EXP-01 A1 evidence assessment

Engineering implementation: **PASS_WITH_CAVEATS** at clean source commit
`12f3575d9adbc21755c70ec454440ae8b06ba0d4`.
Scientific promotion: **BLOCKED**. This is internal engineering verification by a
separate agent in the same session, not independent external scientific replication.

The delivery commit adds this evidence only. `report.json` records the tested commit,
empty diff hash, complete source hashes, commands and actual exit codes. Check hosted
CI separately on the delivery commit; no hosted result is inferred from this packet.

| Measurement | Observed result | Authority |
|---|---|---|
| Regression/adversarial tests | 60 passed, 0 errors, skips, xfails or unexpected successes | Engineering verification |
| Fixed mutation calibration | 11/11 assertion-killed, 0 invalid mutants | These 11 falsifiers only; not exhaustive coverage |
| Original PRIMARY | 128 worlds, 1280 arm rows; COUPLED and CENTRAL 122/128; zero exact trace divergence | Internal synthetic diagnostic |
| Analytic estimator fixtures | 27 checks passed | Named analytic components only |
| Local hardware timing | 200 balanced randomized batches, raw wall/CPU intervals | LOCAL_TIMING_ONLY; joules/FLOPs unqualified |
| Pinned BN-Syn | 32 neurons × 1000 ticks × 2 seeds × 3 arms; all-arm replay; exact emulator parity; 96 coupled spikes versus 0 with zero action per seed | Actual integration smoke; no neural efficacy claim |
| Scientific and physical-cost admission | Requested gates exit 2 | Correctly blocked |

The original four frozen files are byte-identical to PR head `4ccb02e7`.
The amendment and numerical qualification contracts precede new probes in Git history.
Original thresholds, cohorts and primary contrasts were not tuned.

## Defects demonstrated and repaired

- Original trace hashing rounded to 12 decimal places; adjacent binary64 values could
  collide. New exact float.hex encoding and one-ULP fault test enforce the stated invariant.
- Memory proxy was reported without enforcing its envelope. A zero budget still passed;
  the boundary now rejects that condition without pretending the proxy measures RAM.
- Six representative re-signed sidecar lies passed the original verifier. Exact replay
  now checks every derived field, type and field roster, including safety/cost/authority.
- Timing previously checked only the final result of the final repeat. A transient
  corrupted emulator result was overwritten. Every timed result is now checked.
- A common-mode controller defect could exceed the physical actuator bound while
  total effort stayed inside its budget. The plant boundary now rejects the action.
- Concurrent writers could pass the empty-directory check and overwrite evidence.
  Exclusive directory reservation now permits only one writer.
- Neural responsiveness cannot be established by changed action labels alone. The
  state-response control rejects an actual actuator-disconnected BN-Syn execution.

Baseline failures, adversarial reproductions and their resolved checks are retained
in `negative-evidence/`. An initial verification detected source drift during active
documentation edits and returned nonzero; that negative remains archived. Final
verification ran on the clean committed source and recorded no drift.

## Scientific boundary

The frozen positive conjunction includes `LCB(COUPLED-CENTRAL)>0.05`, while faithful
parity fixes every paired difference at zero. At N=128 its bound is
`-0.27350422022515386`. Completing missing instruments or replication cannot satisfy
that conjunction. A restricted-comparator claim needs a separately preregistered
lineage and untouched cohorts; this lineage's negative control remains intact.

Remaining external work: calibrated resource vector under identical physical
interfaces, externally authenticated independent blind execution, a prospective
neural goal/OOD efficacy protocol, and estimator qualification for that actual data
and intervention. The current integration run does not close these scientific gates.

## Verify this packet

```sh
(cd artifacts/cneh-exp-01-a1 && sha256sum --check SHA256SUMS)
python experiments/cneh_exp_01/run.py --out artifacts/cneh-exp-01-a1/primary --verify
python experiments/cneh_exp_01/qualification.py --bundle artifacts/cneh-exp-01-a1/primary --require-scientific-readiness
```

The last command must exit 2. `VERIFIER_SHA256SUMS` preserves the separate verifier's
original packet manifest; the enclosing manifest also covers the added assessment,
dependency installation receipt and archived negatives. Full reconstruction commands
are in `experiments/cneh_exp_01/QUALIFICATION_GUIDE.md`.
