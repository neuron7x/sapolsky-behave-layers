# Acceptance-auditor remediation A3

Engineering amendment, 2026-11-23. Original scientific protocol, thresholds,
cohorts, comparators and all preserved evidence remain unchanged.

The A2 evidence delivery `f5625363f72be3652d6b6e6fbfad1ceeac57e857`
contains a historical acceptance-auditor prototype with an unsafe `--refresh`
path. Its SHA256 is
`fabdb74ac9572086a847c0486da10039f00ae4a89e46c08d9eeeff9bd26862d1`.
An independent counterexample supplies an empty checkout and self-authored
manifest/receipt, obtaining cached G3/G4 PASS without executing replay. G1/G2
were explicitly mocked PASS to isolate this defect. The genuinely executed
fresh replay remains evidence; the cached acceptance mechanism is disqualified.
No ENGINEERING_QUALIFIED disposition has been issued.

The A2 artifact and failed probe must remain intact. The authoritative replacement
is `experiments/cneh_exp_01/acceptance.py`; the A2 prototype must not be used for
admission. This is a repair to acceptance tooling, not a new scientific hypothesis
or retrospective change to any experimental threshold.

Frozen engineering obligations before the replacement implementation:

- Eliminate cached admission and the `--refresh` CLI path entirely.
- Every qualifying invocation executes fresh G3 reconstruction/replay and G4
  epistemic checks; no caller-authored status field can replace execution.
- Reserve a new output directory atomically. Reject any existing directory,
  symlink or forged saved receipt without overwriting it.
- A repeated/concurrent writer must fail. Preserve the original failed probe.
- Missing, pending, skipped, neutral or failed required CI remains non-PASS.
- Keep every original execution log and immutable A1/A2 bundle unchanged.
- Run the regression against the original prototype (demonstrated failure) and
  the replacement (rejection), including a real fresh invocation on the final SHA.

Final engineering acceptance remains G1 AND G2 AND G3 AND G4 on one final SHA.
Scientific promotion remains blocked; external replication is NOT_TESTED.
