# L4j Sub-Line Consistency Audit — RESULTS

**Verdict: `L4J_CONSISTENT`.** Preregistration:
`experiments/wp3_plasticity_v12_consistency/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v12_consistency.src.consistency`.

## Result

Every `CWC-L4*` claim's **registry status matches its artifact verdict polarity**, and no L4
evidence bundle is orphaned from the registry:

- **L4 claims checked:** 9 scientific claims (the auditor **self-exempts** `CWC-L4j` — auditing
  its own verdict is circular; the orphan check likewise exempts the auditor's own bundle).
- **Polarity mismatches:** 0 — no SUPPORTED claim rests on a negative verdict, and no
  NOT_SUPPORTED claim on a positive one.
- **Orphan evidence bundles:** 0 — every `artifacts/wp3-plasticity-v*` bundle with a
  `verdict.json` is referenced by a registry claim.

## Why this check exists

`doc_status_gate` verifies claim↔hypothesis linkage; `validate_evidence` verifies bundle
structure and JSON finiteness. Neither checks that a claim's **status agrees with its own
evidence's verdict**. Across a dozen hand-maintained L4 claims that gap is exactly where drift
would hide (a positive silently registered on a falsification, or a stale artifact). This audit
closes it, and it **can fail** (a mismatch or orphan flips the verdict to `L4J_INCONSISTENT`).

## Consequence for the claim ladder

`CWC-L4j-line-consistency` is registered **SUPPORTED**: the L4 sub-line is internally consistent
(registry ⟺ evidence). A governance guarantee for the whole study. Frozen.

## Scope

Process/governance check (tier: PROCESS). Not a scientific capability claim.
