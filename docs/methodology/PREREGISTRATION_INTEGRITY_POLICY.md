# Preregistration Integrity Policy

Effective 2026-07-19. This policy is prospective; it cannot repair historical
temporal provenance.

## A protocol qualifies as preregistered only if all conditions hold

1. The protocol, primary estimand, exclusions, seed count, stopping rule,
   analysis code hash, and decision rule are committed before any confirmatory
   output is generated.
2. The protocol commit is signed or anchored by an external immutable timestamp.
3. The results commit is a strict descendant of the protocol commit and is not
   the same commit.
4. Pilot data are identified by immutable IDs and excluded from confirmatory
   inference.
5. Deviations are appended; the original protocol is never overwritten.
6. Failure of any condition forces the label `RETROSPECTIVE_PROTOCOL` or
   `EXPLORATORY`, never `PREREGISTERED`.

## Current historical classification

- WP3 plasticity v1: `RETROSPECTIVE_PROTOCOL`.
- WP4 archived run: theory predates the run, but experiment protocol and results
  share a commit; `RETROSPECTIVE_PROTOCOL`.
- Routing-v3 REINFORCE: `RETROSPECTIVE_PROTOCOL`.
- Routing-v3 surface-matched: `RETROSPECTIVE_PROTOCOL`.
- WP4 v2: `POST_AUDIT_CORRECTIVE_NOT_PREREGISTERED`.

No future claim may use “preregistered” based only on prose or an author-supplied
date. Git/external timestamp order is the evidence.
