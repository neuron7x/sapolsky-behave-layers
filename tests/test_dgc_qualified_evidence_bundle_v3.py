from __future__ import annotations

from pathlib import Path

import cwc.governance.qualified_evidence_bundle as qeb


def test_verification_transcript_graph_includes_plan_entrypoint_and_raw_subjects(tmp_path: Path, monkeypatch):
    report_rel = "artifacts/dgc-product-v1/generated/swe/report.json"
    report = tmp_path / report_rel
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        qeb,
        "load_p19_verification_report",
        lambda path, repository_root: {
            "verification_plan_path": "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V1.json",
            "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
            "checks": [
                {
                    "check_id": "PRIMARY_P9_RAW_REPLAY",
                    "receipt_path": "artifacts/dgc-product-v1/generated/swe/check.json",
                    "stdout_path": "artifacts/dgc-product-v1/generated/swe/check.stdout",
                    "stderr_path": "artifacts/dgc-product-v1/generated/swe/check.stderr",
                    "evidence_path": "artifacts/dgc-product-v1/generated/swe/check.evidence.json",
                }
            ],
        },
    )

    paths, zero_ok = qeb._collect_verification_transcript_paths(tmp_path, report_rel)
    assert paths == {
        report_rel,
        "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V1.json",
        "scripts/dgc_external_p19_verifier.py",
        "artifacts/dgc-product-v1/generated/swe/check.json",
        "artifacts/dgc-product-v1/generated/swe/check.stdout",
        "artifacts/dgc-product-v1/generated/swe/check.stderr",
        "artifacts/dgc-product-v1/generated/swe/check.evidence.json",
    }
    assert zero_ok == {
        "artifacts/dgc-product-v1/generated/swe/check.stdout",
        "artifacts/dgc-product-v1/generated/swe/check.stderr",
    }


def test_bundle_v3_declares_plan_and_entrypoint_as_mandatory_graph_vertices():
    assert qeb.SCHEMA == "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V3"
    fields = qeb.QualifiedEvidenceBundleAuthority.__dataclass_fields__
    assert "raw_p19_verification_transcripts_included" in fields
    assert "frozen_verification_plan_and_entrypoint_included" in fields
