# Dual-Sided Verifier and Abstention Gate v1

Scope: one canonical CWC closure, not a programme-wide production promotion.
No scientific claim, frozen negative, P19 activation policy or
`PRODUCT_QUALIFIED` predicate is changed.

## Contract

`make -f Makefile.cwc dual-sided-verifier-gate` runs the same admission check
included additively in `verify` and `pr-fast` (and therefore `pr-full`).
It separately records artifact quality, decision correctness, coverage,
execution integrity and fresh-process replay. No aggregate score can hide a
failed component. Empty, partial or exception-only evidence cannot pass.
The two new runtime modules have a mandatory 100% statement/branch coverage
floor in this target; this is not a coverage claim about the entire repository.

The first integration is **memory-free finite-world CWC plan admission**:

1. Receive immutable JSON request bytes and their caller-frozen SHA-256.
2. Reject ambiguous duplicate keys, non-finite/bool utilities, malformed
   identity, mismatched action sets, unbounded inputs and extra top-level fields.
3. Recompute the certificate using the existing `plan_counterfactual` runtime.
4. Independently check world bindings, certificate integrity and the decision
   using exhaustive pairwise utility inequalities, without calling the planner.
5. Call the executor once per invocation only when both implementations agree
   on `PASS + SUBMIT + selected_action`; otherwise never call it.

| Artifact quality | Executable decision | Meaning |
| --- | --- | --- |
| PASS | SUBMIT | Certified margin-separated action in every supplied world |
| PASS | STOP | Shared nominal winner lacks the required margin |
| PASS | ESCALATE | Supplied worlds demand incompatible actions |
| FAIL | STOP | Invalid, stale, altered or semantically false certificate |
| UNKNOWN | UNRESOLVED | Unsupported schema or unavailable memory/information authority |

`ESCALATE` is machine-routable; this change introduces no mandatory human
reviewer. It is not permission for another component to silently resume execution.

## Frozen qualification evidence

`tests/fixtures/dual_sided_planner.json` contains 20 byte-exact, pinned cases.
The verifier and critic receive only the payload, never case IDs or expected
labels. There is one canonical positive and three positive variants:

| Variant | Declared equivalence |
| --- | --- |
| World/action ordering and JSON formatting | Same finite decision problem |
| Redundant agreeing world | Same conjunction of action-safety constraints |
| Uniform utility translation | Same pairwise differences and margin |

Other cases cover both sides of the margin, ties, honest contradiction,
unknown authority, malformed input, changed/dropped worlds, duplicate keys,
NaN, and self-rehashed false decisions. Reject-all, accept-all,
contradiction-to-submit and crash mutants must all fail qualification.
An additional seeded 300-panel differential test exercises action names, ties,
multi-world disagreement and margins outside the frozen suite.

The runner executes the fixed suite and controls in two fresh processes with
different `PYTHONHASHSEED` values. It requires exact report equality and unchanged
source identity before/after. Content-addressed receipts bind the fixture bytes,
all CWC Python source bytes, gate/tests, Makefile, dependency contracts, Git
commit/tree, dirty-worktree flag and Python version. Existing unequal evidence
is never overwritten. A dirty run is a worktree-content result, not proof of
the named commit alone. CI must run again at the final PR SHA.

## Runtime use

```python
from cwc.governance.planner_admission import execute_verified_plan

result = execute_verified_plan(
    request_bytes,
    expected_input_sha256=frozen_request_sha256,
    executor=execute_action,
)
```

The document schema is `CWC_MEMORY_FREE_PLAN_ADMISSION_V1` with exactly
`schema`, `context_scope`, `worlds`, `certificate`. The certificate is the native
`PlanCertificate.payload()` plus `certificate_digest`; each world has exactly
`world_id`, `utilities`, `provenance`. The adapter does not mint memory authority.

## Evidence boundary / UNKNOWN

- Acceptance is conditional on supplied worlds, utilities and context. A caller
  that changes the entire frozen problem and its expected digest is outside
  this binding; completeness/truth of the world set is not established.
- Utilities use the native planner's binary64 normalization, not exact-real or
  arbitrary-precision integer arithmetic. Values collapsed by rounding do not
  become distinguishable evidence; the declared margin is evaluated accordingly.
- The critic is algorithmically separate but shares input validation and JSON
  encoding. This is not social independence or complete common-mode protection.
- Distinct fixture bytes do not prove semantic coverage. Equivalences are the
  declared, reviewed transformations above, not an automatic equivalence proof.
- No external side effects, rollback, cross-hardware replay, concurrent mutation,
  general memory-dependent planning, or production safety is qualified here.
- The callback is invoked at most once **per invocation**. Distributed exactly-once
  delivery, persistence, retry deduplication and irreversible-action recovery
  remain external responsibilities. Callback failures propagate without retry.
- No new runtime dependencies, broader scientific authority or release privilege
  is introduced. Adoption elsewhere needs its own domain-specific fixture oracle.
