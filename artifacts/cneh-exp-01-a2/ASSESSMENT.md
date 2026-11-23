# CNEH-EXP-01 A2 execution evidence

Repository: `neuron7x/sapolsky-behave-layers`; branch: `research/cneh-exp-01`; PR43.
Implementation commit: `f030a12b145bd8b43876c9e2d8b268e820e92b87`.
The delivery adds evidence only. PR44 is unchanged at
`d0eada284220c4dad759191f5a847139a2dcb999` and remains a separate lineage.

## Acceptance is a conjunction, never a test-count vote

`ENGINEERING_QUALIFIED = G1 AND G2 AND G3 AND G4`. UNKNOWN is not PASS.
This packet supplies source-bound execution evidence. It does not alone assert
qualification of a later delivery SHA. The final local acceptance receipt must
record all four gates on the delivery SHA, outside the commit it measures:

- G1: local `git status --porcelain=v1 --untracked-files=all` empty, canonical remote
  branch SHA equal to local HEAD, and zero unpublished commits. GitHub API alone
  cannot establish this local condition.
- G2: explicit nonempty expected inventory and every applicable check-run completed
  successfully on that same SHA. A successful CodeQL upload is insufficient if the
  separately emitted CodeQL analysis result fails. Missing or pending checks block.
- G3: actual replay from a clean Git materialization, checked manifests and exact
  implementation/source/dependency bindings. Hash consistency alone is insufficient.
- G4: frozen scientific statuses and negative results preserved; engineering evidence
  never authorizes `SUPPORTED_NARROW` under the exact-emulator comparator.

No branch protection is currently configured on main (API404, independently queried).
The acceptance inventory is explicitly required even without a server-side rule;
absence of configured rules does not produce vacuous PASS.

## Executed scope and repaired defects

A2 reuses PR44's pinned `linear_reference.py` and existing CWC causal code. It adds
an authenticated qualification boundary, independent block/SVD/linear-solve oracles,
exact SCM countermodels and a separate fixed seven-mutant calibration. It does not
implement a competing experimental controller or change PR44's history.

The preserved counterexamples include finite Hankel cancellation that destroys a
small nonzero singular value, a full-rank design whose normal-equation Fisher
certificate loses its smallest eigenvalue, observation-only causal equivalence,
training/evaluation leakage and analytic OOD model residuals. Rejection by these
fixtures is bounded numerical qualification, not neural causal validity or a
finite-sample confidence statement. Exact-PMF PID remains analytic-only.

Hardware metrology reuses the synchronous timing harness and adds fresh per-arm
process RSS, separate controller/serialization profiling, dispatch and verifier
costs. Every included ceiling affects admission. Seven re-signed substitutions of
nested reports, source identities, RSS claims, stdout sizes and monotonic intervals
were independently rejected. A GPU inventory defect that misclassified display
connectors was reproduced and repaired; both failure and success logs are retained.

The independently executed local measurement recorded 20 workers and 80 isolated
seed batches: median wall latencies across arms 124.050–150.502 microseconds/call,
peak RSS 32,129,024 bytes including interpreter/import/warmup. Actual paired medians:
CENTRAL 139.024 and COUPLED 146.995 microseconds/call on the shared i5-12500H host.
These are descriptive timing observations, not a resource-parity or advantage claim.
Raw vectors, power/OS/runtime identity and clock boundaries are in the report.

`verification/` contains actual command exits, 74 standard tests, 14 numerical tests,
11 + 7 assertion-killed mutants, 45 numerical checks, source reconstruction and
executed primary/neural replays. The verifier is a separate agent in this session;
this is not independent external scientific replication.

The initial strict checkout roster check found two Python bytecode files generated
by the isolated metrology workers. It found no modified tracked file. The negative
receipt is retained; the final adjudication compares both exact cache bytes against
independent compilation of the pinned source. No arbitrary untracked source is
admitted. Dependency checks retain their initial diagnostic failure and corrected
receipt; the final check verifies the hash-locked installation and 2488 RECORD files.

## Provenance and evidence map

`evidence-map.json` maps each bounded claim to its assumptions, exact implementation
and test location/hash, result artifact/hash and concrete falsifier. `SHA256SUMS`
covers this delivery. The previous A1 packet is reused by hash and remains unchanged;
its 1280 primary rows and actual BN-Syn traces are replayed by the current source.

Digests authenticate content only relative to an independently obtained trusted
commit. Recomputing an attacker's complete manifest does not establish provenance.
The regression verifier recomputes semantic outcomes from trusted source; plausible
forged timing measurements still require trusted execution or external metrology.
No unvalidated signing identity or fabricated certificate is used.

The source commit passed all 15 GitHub check-runs; their exact-SHA API receipts
and the complete successful repository gate log are retained in `source-ci/`.
The final delivery is checked again with `acceptance-auditor.py`; its 17 negative
and positive self-checks reject missing, skipped, neutral, failed or pending CI.

The portable package includes frozen source, the pinned external source scope,
locks, raw outputs, recomputation commands, checksums and a machine-readable
replication disposition. Its actual extraction/replay receipt is archived: final r3 has 190 files,
47 canonical source files and 17 executed commands; four source/provenance tamper
controls reject, and source/package bytes remain unchanged. Archive SHA256:
`df311241fe4b50c1d283c44b1cab902c50d45ee7c05656c2468dc8508eebe6ca`.
No sealed external seed cohort or operator identity has been invented. The existing
commitment CLI prepares/seals/verifies bindings; it does not execute a blind cohort.

## Scientific disposition and remaining falsifiers

`CNEH-04-DC: FORMALIZED / EMPIRICAL VALIDATION PENDING`.
Scientific promotion is BLOCKED. `REPLICATION_NOT_TESTED` and
`COST_INSTRUMENT_INVALID` remain in force. Source-bound analytic qualification does
not replace estimator qualification for the intended neural data.

| Remaining obligation | Evidence required to close it |
|---|---|
| Frozen positive central contrast | Structurally unreachable: exact parity forces every paired difference to 0; frozen LCB is -0.27350422022515386, below +0.05. Keep the negative control; use a separately preregistered restricted-comparator lineage for another question. |
| Physical resource parity | Paired complete measured vectors under identical interfaces, including model training, communication and centralized execution; calibrated joules/hardware operation channel. Matched ceilings do not establish parity. |
| External replication | Authenticated distinct operator; externally committed disjoint blind seeds before execution; output publication before reveal; complete frozen-protocol replay and independent evaluation. |
| Functional neural coupling | Actual interpopulation coupling intervention with physical response and countercontrols. Zero-action responsiveness is insufficient. |
| Structural neural OOD and task efficacy | Prospective structural shift and causal closed-loop goal estimand, separately preregistered; fresh evaluation data. |
| Neural causal/PID estimator | Fixed target and decomposition, sampling/noise assumptions, nulls, bias and uncertainty qualification, tolerances and ablations on the intended data. |

The neural smoke closes API integration, within-environment exact replay and actual
spiking only. It does not close the last three neural obligations. Calibrated energy,
physical FLOPs and real transport instruments remain invalid. No claim of exceeding
an academic standard or holding an industrial certification is made.
