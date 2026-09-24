# DGC Deterministic Release Assurance v1

Status: `BUILDER_IMPLEMENTED / CURRENT PRODUCT RELEASE NOT AUTHORIZED`

## Why a DGC-specific release spine exists

The historical root `RELEASE_MANIFEST.json` is anchored to an earlier WP16 clean-room commit and is not current DGC authority. The historical `scripts/make_release.py` also predates the DGC proof/evidence topology.

DGC therefore uses `scripts/make_dgc_release.py` for research/product handoffs.

## Deterministic archive contract

The builder:

1. requires a clean tracked Git working tree by default;
2. binds exact `HEAD` and `HEAD^{tree}`;
3. enumerates tracked files through Git rather than host-directory traversal;
4. separates tracked `artifacts/**` evidence from the rest of the tracked source tree;
5. normalizes tar uid/gid/user/group/mtime/mode semantics;
6. sets gzip mtime to zero;
7. sorts paths deterministically;
8. hashes source/evidence archives with SHA-256;
9. binds critical evidence, proof-ledger, workflow, SBOM and citation digests;
10. emits `DGC_RELEASE_MANIFEST.json` and `SHA256SUMS`.

`dgc_release_repro_gate.py` builds the same clean Git tree twice into independent temporary directories and requires byte-identical artifacts and identical manifests.

## Authority separation

The manifest derives product qualification from the same canonical fields used by `ProductEvidenceRecord.product_qualified`.

`PRODUCT_QUALIFIED` does **not** imply production-control authority. Provider trace, shadow qualification and bounded canary remain additional gates.

When current evidence is incomplete, the builder must label the output:

`RESEARCH_RELEASE_NOT_PRODUCT_QUALIFIED`

This is a valid research handoff, not a product release.

## Current targeted authority

Deterministic tar/gzip unit tests: `2/2 PASS` locally.

Full double-build reproducibility on the exact current Git tree remains dependent on a runnable clean checkout. GitHub Actions continues to terminate before repository steps in the current environment, so remote release-repro authority is not yet claimed.
