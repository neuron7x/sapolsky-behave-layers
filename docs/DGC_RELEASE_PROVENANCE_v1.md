# DGC Release Provenance Protocol v2

Status: **PRE-OUTCOME / FAIL-CLOSED DESIGN AUTHORITY**

This document defines the separation between the source revision under which evidence is generated and the later revision used only to package that evidence. It does **not** claim SLSA conformance or any product result.

## 1. Two immutable identities

DGC uses two different Git subjects.

### `T_exec` — qualified execution source identity

`T_exec` is the immutable Git commit/tree under which external workloads, scoring, statistical inference, CCF, fault injection, independent replication and the frozen external-verification protocol are defined.

The evidence-closure ledger, P9, G1–G5, fault authority, replication authority and both family P19 roots bind to this identity.

No executable, statistical, scorer, model-policy, budget, pricing, preregistration, theorem, verifier-plan, verifier-entrypoint or workflow source may change after outcome-bearing execution begins.

### `T_pkg` — evidence packaging identity

`T_pkg` is a descendant revision created only after the evidence closure for `T_exec` has reached its terminal product stage.

It may add disclosed evidence under approved evidence-only namespaces and may update only explicitly non-scientific terminal metadata such as the qualification pointer and informational evidence-status mirror.

`T_pkg` is **not** allowed to redefine the method that generated or verified the observations.

## 2. Required temporal order

The admissible order is:

```text
freeze method + P19 verifier plan + external-verifier trust policy
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
8-check external semantic replay per family
        ↓
canonical receipts + stdout + stderr + evidence subjects
        ↓
SSH-signed P19 attestations under frozen trust policy
        ↓
Global V5 portable semantic replay
        ↓
ledger reaches PRODUCT_QUALIFIED under T_exec
        ↓
create post-outcome evidence packaging revision T_pkg
        ↓
activate Pointer V3 and add only evidence-only subjects
        ↓
verify T_exec is ancestor of T_pkg
        ↓
verify diff(T_exec,T_pkg) against append-only packaging policy V2
        ↓
derive graph-complete qualified evidence bundle V4
        ↓
double-build deterministic portable release V6
```

Changing this order invalidates product promotion.

## 3. Portable terminal signature semantics

A valid SSH signature is a cryptographic relation between the signed attestation bytes, signature bytes, verifier principal/namespace and frozen trust store. The path and binary hash of the local `ssh-keygen` executable are useful forensic execution provenance, but they are not part of portable scientific product truth.

Global V5 therefore binds the stable signature inputs and PASS result:

- family P19 digest;
- verifier principal;
- attestation SHA-256;
- verification-report SHA-256;
- signature SHA-256;
- allowed-signers SHA-256;
- SSH namespace;
- `signature_verified=true`.

It deliberately excludes machine-local `ssh-keygen` path/binary/stdout/stderr from the Global V5 authority digest while still executing signature verification fail-closed.

Canonical implementation:

`cwc/governance/global_product_qualification_v5.py`

## 4. Append-only packaging policy

Canonical implementation:

`cwc/governance/evidence_packaging_authority.py`

Policy identity:

`DGC_APPEND_ONLY_POST_OUTCOME_PACKAGING_POLICY_V2_GLOBAL_V5`

Post-outcome additions are restricted to:

- `artifacts/dgc-product-v1/generated/`
- `artifacts/dgc-product-v1/evidence/`
- `eval_bundle/`
- `release_evidence/`

Only the following existing non-method files may be modified:

- `artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json`
- `artifacts/dgc-product-v1/evidence_status.json`

Deletion, type change, source modification, methodology modification, verifier-plan modification, mode change, symlink/special object, ambiguous path or addition outside evidence-only namespaces is a hard failure.

## 5. Graph-derived bundle completeness

A fixed filename checklist is insufficient for product qualification.

Canonical implementation:

`cwc/governance/qualified_evidence_bundle.py`

Current authority:

`DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V4`

The release evidence graph is derived from the actual authority chain:

```text
Pointer V3
  ├─ qualification ledger
  ├─ portable Global V5
  ├─ source registry
  ├─ frozen verifier policy / signer trust store
  └─ 2 × family P19
       ├─ stage evidence
       ├─ methodology anchors
       ├─ raw subject roots
       ├─ verification reports
       ├─ attestations
       ├─ signatures
       └─ external-verification transcript
            ├─ frozen verification plan
            ├─ verifier entrypoint
            └─ 8 × check
                 ├─ canonical check receipt
                 ├─ stdout bytes
                 ├─ stderr bytes
                 └─ replay evidence bytes
```

Every required file belongs to one of exactly two classes:

1. `EXECUTION_SOURCE_T0` — the same Git blob exists in `T_exec` and `T_pkg`.
2. `PACKAGING_EVIDENCE_T1` — the file is an approved post-outcome packaging subject tracked in `T_pkg`.

An untracked raw result, omitted verifier transcript, omitted frozen plan/entrypoint, mutated source anchor or post-hoc file outside approved evidence namespaces makes the qualified bundle incomplete.

## 6. Release artifacts

A product-qualified release contains separate roles:

- `dgc-execution-source-<T_exec>.tar.gz` — generated deterministically from immutable Git objects, not packaging HEAD;
- `dgc-packaging-evidence-<T_pkg>.tar.gz` — tracked evidence/metadata from the packaging revision;
- `DGC_EVIDENCE_PACKAGING_AUTHORITY.json`;
- `DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY.json`;
- `DGC_RELEASE_MANIFEST.json`;
- `SHA256SUMS`.

Current release schema:

`DGC_DETERMINISTIC_RESEARCH_RELEASE_V6`

The release manifest records both commit/tree identities and explicitly states that environment-specific signature-tool execution provenance is not product authority.

## 7. Product versus production

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

## 8. Supply-chain reference boundary

The design follows the general provenance principle that artifacts should be traceable to immutable source revisions and that source revisions should be uniquely identifiable. SLSA v1.2 describes provenance as verifiable information connecting an artifact to where/how it was produced, and its Source track treats digest-identified Git revisions as immutable revision identities.

References:

- https://slsa.dev/spec/v1.2/provenance
- https://slsa.dev/spec/v1.2/source-requirements

DGC currently sets:

```text
slsa_conformance_claim = false
```

These references justify the provenance separation pattern only; they do not constitute an audit or SLSA level claim.

## 9. Current activation boundary

The canonical terminal pointer is:

`artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json`

It is currently fail-closed with `activation_authorized=false` and `product_qualified_claimed=false`. The verifier trust policy is also not activated with real external keys.

Until real external verifier identities are frozen **before** outcome-bearing execution and the empirical campaign is completed:

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
```
