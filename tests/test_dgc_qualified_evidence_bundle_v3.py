from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cwc.governance.qualified_evidence_bundle as qeb


def test_verification_transcript_graph_includes_plan_runtime_regression_and_raw_subjects(tmp_path: Path, monkeypatch):
    report_rel = "artifacts/dgc-product-v1/generated/swe/report.json"
    plan_rel = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V3.json"
    regression_rel = "artifacts/dgc-product-v1/verifier-regression/receipt.json"
    regression_stdout = "artifacts/dgc-product-v1/verifier-regression/stdout.bin"
    regression_stderr = "artifacts/dgc-product-v1/verifier-regression/stderr.bin"
    regression_test = "tests/test_dgc_p19_external_replay.py"

    for rel, data in (
        (report_rel, "{}\n"),
        (plan_rel, "{}\n"),
        (regression_rel, "{}\n"),
        (regression_stdout, "PASS\n"),
        (regression_test, "# test\n"),
        ("scripts/dgc_external_p19_verifier.py", "print('verify')\n"),
        ("cwc/governance/p19_external_verification_contract.py", "# contract\n"),
        ("cwc/governance/p19_external_replay.py", "# replay\n"),
        ("artifacts/dgc-product-v1/generated/swe/check.json", "{}\n"),
        ("artifacts/dgc-product-v1/generated/swe/check.stdout", "PASS\n"),
        ("artifacts/dgc-product-v1/generated/swe/check.evidence.json", "{}\n"),
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    for rel in (regression_stderr, "artifacts/dgc-product-v1/generated/swe/check.stderr"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")

    monkeypatch.setattr(
        qeb,
        "load_p19_verification_report",
        lambda path, repository_root: {
            "verification_plan_path": plan_rel,
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
    monkeypatch.setattr(
        qeb,
        "load_p19_external_verification_plan",
        lambda *args, **kwargs: SimpleNamespace(
            verifier_dependencies=(
                {"path": "cwc/governance/p19_external_verification_contract.py"},
                {"path": "cwc/governance/p19_external_replay.py"},
            ),
            activation_regression_receipt_path=regression_rel,
            activation_regression_receipt_digest="d" * 64,
        ),
    )
    monkeypatch.setattr(
        qeb,
        "verify_p19_external_verifier_regression_receipt",
        lambda *args, **kwargs: {
            "receipt_digest": "d" * 64,
            "runtime_manifest": [
                {"path": "scripts/dgc_external_p19_verifier.py"},
                {"path": "cwc/governance/p19_external_verification_contract.py"},
                {"path": "cwc/governance/p19_external_replay.py"},
            ],
            "test_manifest": [{"path": regression_test}],
            "stdout_path": regression_stdout,
            "stderr_path": regression_stderr,
        },
    )

    paths, zero_ok = qeb._collect_verification_transcript_paths(tmp_path, report_rel)
    assert paths == {
        report_rel,
        plan_rel,
        "scripts/dgc_external_p19_verifier.py",
        "cwc/governance/p19_external_verification_contract.py",
        "cwc/governance/p19_external_replay.py",
        regression_rel,
        regression_stdout,
        regression_stderr,
        regression_test,
        "artifacts/dgc-product-v1/generated/swe/check.json",
        "artifacts/dgc-product-v1/generated/swe/check.stdout",
        "artifacts/dgc-product-v1/generated/swe/check.stderr",
        "artifacts/dgc-product-v1/generated/swe/check.evidence.json",
    }
    assert zero_ok == {
        regression_stderr,
        "artifacts/dgc-product-v1/generated/swe/check.stdout",
        "artifacts/dgc-product-v1/generated/swe/check.stderr",
    }


def test_bundle_v6_declares_regression_portable_replay_and_verifier_dependency_closure():
    assert qeb.SCHEMA == "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V6"
    fields = qeb.QualifiedEvidenceBundleAuthority.__dataclass_fields__
    assert "raw_p19_verification_transcripts_included" in fields
    assert "frozen_verification_plan_and_entrypoint_included" in fields
    assert "frozen_verifier_dependency_closure_included" in fields
    assert "activation_regression_evidence_included" in fields
    assert "portable_p19_replay_inputs_included" in fields
    assert "portable_global_v5_authority_included" in fields
