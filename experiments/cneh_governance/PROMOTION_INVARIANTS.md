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
