# PREREGISTRATION — L4j Sub-Line Consistency Audit

**Committed before the run.** The L4 sub-line now spans a dozen claims maintained by hand across
`claim_registry.json`, per-experiment `verdict.json`, and `SYSTEM.md`. This is a machine
cross-check that the **registry status matches each artifact's verdict** (no drift, no
mislabeled positive/negative) — a governance check the existing gates do not perform.

## Design (frozen)

- Enumerate every claim whose id starts with `CWC-L4` in `claim_registry.json`.
- For each, locate the `verdict.json` in its `required_artifacts` (if any) and read its
  `verdict`/`status` string.
- Classify **polarity**: registry `SUPPORTED`/`SUPPORTED_NARROWED` = positive,
  `NOT_SUPPORTED` = negative, `NOT_TESTED` = untested. Verdict-string polarity: positive if it
  contains any of {CONFIRMED, SUPPORTED, MAPPED, GENERALIZES, ROBUST, GO} and NOT a negation
  token; negative if it contains any of {VIOLATED, INCOMPLETE, NOT_SUPPORTED, NOT_MAPPED,
  NOT_CONFIRMED, VOID}.
- Assert, for every L4* claim with an artifact verdict, **registry polarity == verdict
  polarity**; and that no `artifacts/wp3-plasticity-v*` bundle with a `verdict.json` lacks a
  registry claim (no orphan evidence).

## Decision rule (FROZEN)

- **L4J_CONSISTENT** iff 0 polarity mismatches AND 0 orphan L4 evidence bundles.
- **L4J_INCONSISTENT** — any mismatch or orphan (registry drifted from evidence).

## Scope / prohibited

Governance/meta check of the L4 sub-line's internal consistency (tier: process). New claim
`CWC-L4j-line-consistency`. Not a scientific capability claim.
