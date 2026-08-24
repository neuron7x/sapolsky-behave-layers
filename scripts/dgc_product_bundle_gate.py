from __future__ import annotations

from pathlib import Path

from cwc.governance.qualified_evidence_bundle import build_qualified_evidence_bundle_authority

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        qualification, packaging, bundle = build_qualified_evidence_bundle_authority(repository_root=ROOT)
    except RuntimeError as exc:
        print(f"DGC-PRODUCT-BUNDLE-GATE: FAIL qualified-evidence-graph: {exc}")
        return 1

    if not bundle.evidence_graph_complete or not bundle.all_required_subjects_git_bound:
        print("DGC-PRODUCT-BUNDLE-GATE: FAIL incomplete-qualified-evidence-graph")
        return 1
    if not bundle.raw_p19_verification_transcripts_included:
        print("DGC-PRODUCT-BUNDLE-GATE: FAIL raw-p19-verification-transcripts-missing")
        return 1
    if bundle.qualified_execution_commit != qualification.repo_commit:
        print("DGC-PRODUCT-BUNDLE-GATE: FAIL execution-source-lineage-mismatch")
        return 1
    if bundle.packaging_commit != packaging.packaging_commit:
        print("DGC-PRODUCT-BUNDLE-GATE: FAIL packaging-lineage-mismatch")
        return 1

    print("DGC-PRODUCT-BUNDLE-COMPLETE: true")
    print("DGC-PRODUCT-BUNDLE-RAW-P19-VERIFICATION-TRANSCRIPTS: true")
    print(f"DGC-PRODUCT-BUNDLE-AUTHORITY: {bundle.authority_digest}")
    print(f"DGC-PRODUCT-BUNDLE-MANIFEST: {bundle.required_file_manifest_digest}")
    print(f"DGC-PRODUCT-BUNDLE-EXECUTION-SOURCE-FILES: {bundle.execution_source_file_count}")
    print(f"DGC-PRODUCT-BUNDLE-PACKAGING-EVIDENCE-FILES: {bundle.packaging_evidence_file_count}")
    print(f"DGC-QUALIFIED-EXECUTION-COMMIT: {bundle.qualified_execution_commit}")
    print(f"DGC-EVIDENCE-PACKAGING-COMMIT: {bundle.packaging_commit}")
    print("DGC-PRODUCT-BUNDLE-GATE: PASS graph-derived qualified evidence bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
