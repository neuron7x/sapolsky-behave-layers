# CNEH scientific promotion: mandatory fail-closed boundary

Effective from the EXP04G lineage; additive governance over the merged PR54
(`711315bdbe6ff3f02030db572b58710e9d3f8365`) and its successors.
Do not rewrite historical experiment code, protocols, verdicts or evidence.

**Necessary invariants (AND, never weighted compensation):**

- MULTISCALE_COHERENCE: a prospectively specified, semantically aligned
  cross-scale check; raw and aggregated endpoints remain distinct, temporal
  co-occurrence is preserved, discrepancies and uncertainty are resolved rather
  than hidden by window/phase selection. A descriptive scale audit is not a
  qualified PASS.
- DETERMINISTIC_REPLAY: exact replay on the explicitly declared and fingerprinted
  execution domain; independent executions on every claimed domain must match
  the sealed state/evidence contract. A same-worker exact replay does not grant
  cross-worker authority. Any unexplained bit mismatch is FAIL; absent domain
  qualification is NOT_TESTED.
- EVIDENCE_INTEGRITY: exact subject/protocol/runtime lineage, complete roster,
  authenticated artifact SHA-256 and inner manifest, fail-closed validation and
  preserved unfavorable observations. Hash equality alone is not scientific
  truth. Historical hosted checks have only their documented scope.

Any missing, unknown, invalid, failed, cancelled, incomplete or otherwise
non-PASS invariant blocks scientific promotion. No exception, waiver, positive
aggregate score, engineering CI, or caller-supplied PASS may override this.
All three PASS are necessary, not sufficient: there is no authenticated positive
promotion issuer in this lineage. A future positive issuer requires separate
audited implementation validating actual receipts bound to the same claim,
source, protocol, artifact roster and numerical domain; existing scientific
requirements remain in force.

## Current dispositions

| Contour | MULTISCALE_COHERENCE | DETERMINISTIC_REPLAY | EVIDENCE_INTEGRITY | Promotion |
|---|---|---|---|---|
| EXP04G | NOT_TESTED | NOT_TESTED (same-worker PASS only) | PASS (historical hosted scope) | BLOCKED |
| EXP05 | NOT_TESTED | FAIL (EXP05A forensic cross-run replay) | PASS (historical hosted scope) | BLOCKED |
| Unregistered subsequent contours | NOT_TESTED | NOT_TESTED | NOT_TESTED | BLOCKED |

EXP04G A/B/C separated adaptation and policy mechanisms. This permitted a
bounded **research experiment** (EXP05), not a scientific promotion. EXP05
failed its joint functional target. EXP05M is retrospective evidence; EXP05R
is execution-domain qualification, not restoration of a positive verdict.
The recorded EXP05A cross-run mismatch must not be repaired by rounding,
retuning, switching to a favorable worker, or relabeling approximate replay.

## Executable enforcement

- `python -m scripts.cneh_promotion_gate audit`: inspect tracked CNEH
  experiment Python/JSON, reject direct non-false authority writes and
  nested positive claims, verify anchored EXP04G/EXP05 code is unchanged.
  Exhaustively check the finite gate-status lattice.
- `python -m scripts.cneh_promotion_gate check-verdict --experiment CNEH-EXP-04G --verdict PATH`:
  require a matching explicit negative verdict. Passing this command admits
  negative evidence, not promotion.
- `python -m scripts.cneh_promotion_gate promotion --experiment CNEH-EXP-04G`:
  exits nonzero and emits BLOCKED. Unknown contours also block by default.
- Canonical Makefile verification and the full PR workflow run the guard.
  EXP04G/EXP05 workflows validate their new verdict after replay without
  modifying the original scientific implementation or evidence formats.
  Subsequent contour workflows must use the shared verdict/promotion boundary
  before any authority-bearing publication; the repository scan runs on
  every full PR gate. The negative-only scanner detects literal writes, not
  arbitrary-code noninterference. CI cannot itself enforce administrator
  branch protection; require the full PR gate in repository settings.

Engineering merge of valid negative evidence is allowed. A failed engineering
instrument gate still blocks that experiment's merge under the existing
admission policy. No unresolved promotion status may be converted to PASS.


## Mandatory adversarial ratchet

The initial green guard and tests at `f8677f5b744e7a3e826f167b6b8abfc4045ffcc9`
remain immutable controls. The expanded independent oracle uses literal expected
gate names/statuses, tests JSON exponent overflow and returned-record aliasing,
literal assignment variants, and real Git negative controls (assume-unchanged,
skip-worktree, unrelated identical tree, symlink, historical roster, nested
positive claim). Verify historical object bytes directly; Git diff alone is
not an evidence integrity verifier.

The full PR workflow runs three separate hosted campaigns (Python 3.11/3.12/3.13,
different hash seeds and shuffled test order). Each must reproduce the old
suite's green baseline, falsify the old implementation using the expanded
suite, pass the hardened unmutated baseline, and kill all 24 intentional
mutants across lattice, authority and evidence families. Each candidate runs
in its own process. Import errors, unexpected crashes, incomplete/skipped
tests or timeouts do not count as kills. Save all receipts. No aggregate
majority vote or passing-only reporting. A surviving mutant blocks the
engineering gate until investigated. The finite mutation panel does not prove
general arbitrary-code safety, and no scientific promotion is authorized.

## Independent evidence admission V2

See [frozen seven-axis protocol](EVIDENCE_RATCHET_V2.md). The original 24 x 3
source-mutation campaign remains mandatory. The separate seven-family fault
panel runs 168 single-fault cases per worker (504 total), each through the real
checker with an expected failure category, independent clean controls and an
actual mutated-fixture witness. This is a measured increase in test-panel
cardinality, not a claim of sevenfold scientific validity.

EXP04G/EXP05 now snapshot all file digests before their unmodified native
replay and independently validate the resulting bundle after replay: exact
roster/manifest and preregistration/implementation lineage, negative verdict,
world/episode identities, paired state/RNG/tape signatures, exact duplicate
emulators, current ledger and physical recurrence. The dedicated ratchet
workflow additionally downloads and checks the original pinned historical ZIPs;
receipt JSONs from fresh runs live outside the original experiment bundle.
Historical ZIP expiry blocks that historical check, not a reason to re-sign or
silently substitute a newer artifact. A fresh snapshot is not a signature or
proof of cross-worker portability. The checker is an additional bounded negative
evidence verifier; no arbitrary code or scientific promotion guarantee.
