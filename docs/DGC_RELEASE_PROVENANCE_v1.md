# DGC Release Provenance Protocol v1

Status: **PRE-OUTCOME / FAIL-CLOSED DESIGN AUTHORITY**

This document defines the separation between the source revision under which evidence is generated and the later revision used only to package that evidence. It does **not** claim SLSA conformance or any product result.

## 1. Two immutable identities

DGC uses two different Git subjects.

### `T_exec` — qualified execution source identity

`T_exec` is the immutable Git commit/tree under which external workloads, scoring, statistical inference, CCF, fault injection and independent replication are executed.

The evidence-closure ledger, P9, G1–G5, fault authority, replication authority and both family P19 roots must all bind to this identity.

No executable, statistical, scorer, model-policy, budget, pricing, preregistration, theorem or workflow source may change after outcome-bearing execution begins.

### `T_pkg` — evidence packaging identity

`T_pkg` is a descendant revision created only after the evidence closure for `T_exec` has reached its terminal product stage.

It may add disclosed evidence under approved evidence-only namespaces and may update only explicitly non-scientific terminal metadata such as the qualification pointer and informational evidence-status mirror.

`T_pkg` is **not** allowed to redefine the method that generated the observations.

## 2. Required temporal order

The admissible order is:

```text
freeze method + external-verifier trust policy
        ↓
commit T_exec
        ↓
keep Git HEAD/tree fixed at T_exec
        ↓
materialize + execute external evidence
        ↓
P9 → G1–G5 → fault → independent replication
        ↓
family P19(SWE) + family P19(Terminal)
        ↓
Global V4 semantic replay
        ↓
ledger reaches PRODUCT_QUALIFIED under T_exec
        ↓
create post-outcome evidence packaging revision T_pkg
        ↓
activate Pointer V2 and add only evidence-only subjects
        ↓
verify T_exec is ancestor of T_pkg
        ↓
verify diff(T_exec,T_pkg) against append-only packaging policy
        ↓
derive graph-complete qualified evidence bundle
        ↓
double-build deterministic release
```

Changing this order invalidates product promotion.

## 3. Append-only packaging policy

Canonical implementation:

`cwc/governance/evidence_packaging_authority.py`

Policy identity:

`DGC_APPEND_ONLY_POST_OUTCOME_PACKAGING_POLICY_V1`

Post-outcome additions are restricted to:

- `artifacts/dgc-product-v1/generated/`
- `artifacts/dgc-product-v1/evidence/`
- `eval_bundle/`
- `release_evidence/`

Only the following existing non-method files may be modified:

- `artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V2.json`
- `artifacts/dgc-product-v1/evidence_status.json`

Deletion, type-change, source modification, methodology modification, mode change of an approved mutable file, or addition outside the evidence-only namespaces is a hard failure.

## 4. Graph-derived bundle completeness

A fixed filename checklist is insufficient for product qualification.

Canonical implementation:

`cwc/governance/qualified_evidence_bundle.py`

The release evidence graph is derived from the actual authority chain:

```text
Pointer V2
  ├─ qualification ledger
  ├─ Global V4
  ├─ source registry
  ├─ frozen verifier policy / signer trust store
  └─ 2 × family P19
       ├─ stage evidence
       ├─ methodology anchors
       ├─ raw subject roots
       ├─ verification reports
       ├─ attestations
       └─ signatures
```

Every required file must be one of exactly two classes:

1. `EXECUTION_SOURCE_T0` — the same Git blob exists in `T_exec` and `T_pkg`.
2. `PACKAGING_EVIDENCE_T1` — the file is an approved post-outcome packaging subject tracked in `T_pkg`.

An untracked raw result, a mutated source anchor, or a post-hoc file outside approved evidence namespaces makes the qualified bundle incomplete.

## 5. Release artifacts

A product-qualified release contains separate roles:

- `dgc-execution-source-<T_exec>.tar.gz` — generated from the immutable execution revision, not the packaging working tree.
- `dgc-packaging-evidence-<T_pkg>.tar.gz` — tracked evidence/metadata from the packaging revision.
- `DGC_EVIDENCE_PACKAGING_AUTHORITY.json`
- `DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY.json`
- `DGC_RELEASE_MANIFEST.json`
- `SHA256SUMS`

The release manifest records both commit/tree identities.

## 6. Product versus production

Even a valid two-family qualified release does not authorize production control.

The following remain separate obligations:

- real production-provider traces;
- shadow operation;
- bounded canary;
- sustained operational monitoring;
- client/operational evidence where applicable.

Therefore:

```text
PRODUCT_QUALIFIED ≠ PRODUCTION_CONTROL_AUTHORIZED
```

## 7. Supply-chain reference boundary

The design follows the general provenance principle that artifacts should be traceable to immutable source revisions and that source revisions should be uniquely identifiable. SLSA v1.2 describes provenance as verifiable information connecting an artifact to where/how it was produced, and its Source track treats digest-identified Git revisions as immutable revision identities.

References:

- https://slsa.dev/spec/v1.2/provenance
- https://slsa.dev/spec/v1.2/source-requirements

DGC currently sets:

```text
slsa_conformance_claim = false
```

These references justify the provenance separation pattern only; they do not constitute an audit or SLSA level claim.

## 8. Current activation boundary

The current repository contains fail-closed unconfigured terminal trust/pointer artifacts. Until real external verifier identities are frozen **before** outcome-bearing execution and the empirical campaign is completed:

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
```
