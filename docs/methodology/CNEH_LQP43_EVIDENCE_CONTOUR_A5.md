# A5: historical evidence is a required CI invariant

Engineering amendment, 2026-11-23, under CNEH-LQP-43-v1.0. No scientific
specification, estimand, threshold, comparator or cohort changes.

Remote cosmetic commit 9e1de455 changed the immutable A2 audit script. Its old
manifest rejected the change, and a normal merge followed by an explicit
restoration preserved both the failure and the original bytes. However, the
required checksum step authenticates only consistency with the current manifest.
An attacker can also replace that manifest. The authoritative fresh acceptance
auditor separately checks historical Git blobs; that invariant must also execute
inside mandatory CI rather than depend solely on the final operator invocation.

Add a small offline history guard to the canonical required full gate. Pin the
original scientific files and historical evidence roots to their existing immutable
commits. Require those commits and their ancestry; compare actual checkout files,
including manifests, against the trusted historical Git objects. Reject missing
files, changed bytes, invalid path types and a fully rehashed substituted bundle.
Preserve historical ledger rows while allowing explicit future append-only rows.

Calibrate the guard with real isolated Git repositories and negative interventions.
Keep all prior checksum, semantic replay, mutation and security checks. No scanner
exception or analysis exclusion is authorized by this amendment. Historical scripts
are evidence, not candidates for automatic cosmetic rewriting. A green checksum
alone must not admit rewritten historical evidence.

The final post-commit proof still requires fresh G1–G4 execution, source-aware CI
and preserved scientific limits. This amendment adds an engineering invariant;
it does not authorize independent-replication or scientific-validation claims.
