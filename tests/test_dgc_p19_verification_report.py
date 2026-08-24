from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import CHECK_METHOD_IDS
from cwc.governance.p19_external_verification_plan import (
    REQUIRED_IMPLEMENTATION_DEPENDENCIES,
    SCHEMA as PLAN_SCHEMA,
)
from cwc.governance.p19_verification_attestation import REQUIRED_CHECKS, load_p19_verification_report
from cwc.governance.p19_verification_report import (
    CHECK_RECEIPT_SCHEMA,
    P19VerificationReportError,
    build_p19_verification_report,
    report_bytes,
)


def _p19() -> dict[str, object]:
    return {
        "family_id": "SWE_BENCH_VERIFIED",
        "p19_digest": "1" * 64,
        "repository_commit": "2" * 40,
        "repository_tree": "3" * 40,
        "statistical_plan_digest": "4" * 64,
        "theorem_identity_digest": "5" * 64,
        "methodology_anchor_digest": "6" * 64,
        "stage_evidence_manifest_digest": "7" * 64,
        "subject_root_manifest_digest": "8" * 64,
        "family_evidence_complete": True,
    }


def _sha(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def _active_plan(root: Path) -> Path:
    entry = root / "scripts/dgc_external_p19_verifier.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('test verifier')\n", encoding="utf-8")
    dependencies = []
    for rel in REQUIRED_IMPLEMENTATION_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen verifier dependency: {rel}\n", encoding="utf-8")
        dependencies.append({"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    rows = []
    for check_id in sorted(REQUIRED_CHECKS):
        rows.append({
            "check_id": check_id,
            "method_id": CHECK_METHOD_IDS[check_id],
            "command_template": [
                "python", "scripts/dgc_external_p19_verifier.py", "--check-id", check_id,
                "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
            ],
            "implementation_status": "IMPLEMENTED",
        })
    payload = {
        "plan_generation": "TEST_ACTIVE_PLAN",
        "frozen_pre_outcome": True,
        "activation_authorized": True,
        "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
        "verifier_entrypoint_sha256": sha256_file(entry),
        "verifier_dependency_manifest_digest": sha256_bytes(canonical_json_bytes(dependencies)),
        "verifier_dependencies": dependencies,
        "check_contracts": rows,
        "all_check_implementations_complete": True,
        "product_qualification_authorized": False,
    }
    doc = {"schema": PLAN_SCHEMA, **payload, "plan_digest": sha256_bytes(canonical_json_bytes(payload))}
    path = root / "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V2.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def _p19_file(root: Path) -> Path:
    path = root / "artifacts/dgc-product-v1/generated/swe/p19.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(_p19()) + b"\n")
    return path


def _receipt(root: Path, p19_rel: str, check_id: str, *, status: str = "PASS", forged_command: bool = False) -> Path:
    base = root / "artifacts/dgc-product-v1/generated/verifier" / check_id.lower()
    base.mkdir(parents=True, exist_ok=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes((check_id + ":stdout\n").encode())
    stderr.write_bytes(b"")
    evidence.write_bytes(("{\"check\":\"" + check_id + "\"}\n").encode())
    evidence_rel = evidence.relative_to(root).as_posix()
    command = (
        ["echo", "PASS"]
        if forged_command
        else [
            "python", "scripts/dgc_external_p19_verifier.py", "--check-id", check_id,
            "--p19", p19_rel, "--evidence-output", evidence_rel,
        ]
    )
    payload = {
        "check_id": check_id,
        "status": status,
        "command_argv": command,
        "stdout_path": stdout.relative_to(root).as_posix(),
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr.relative_to(root).as_posix(),
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence_rel,
        "evidence_sha256": sha256_file(evidence),
        "evidence_bytes": evidence.stat().st_size,
        "evidence_digest": _sha(check_id + ":semantic-evidence"),
    }
    doc = {
        "schema": CHECK_RECEIPT_SCHEMA,
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
    }
    path = base / "receipt.json"
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def _fixture(root: Path):
    plan = _active_plan(root)
    p19_path = _p19_file(root)
    p19_rel = p19_path.relative_to(root).as_posix()
    receipts = tuple(_receipt(root, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    return plan, p19_path, receipts


def _build(root: Path) -> dict[str, object]:
    plan, p19_path, receipts = _fixture(root)
    return build_p19_verification_report(
        repository_root=root,
        family_p19=_p19(),
        family_p19_path=p19_path,
        verification_plan_path=plan,
        check_receipt_paths=receipts,
    )


def test_complete_receipt_population_builds_canonical_planned_report(tmp_path: Path):
    report = _build(tmp_path)
    assert {row["check_id"] for row in report["checks"]} == REQUIRED_CHECKS
    assert report["raw_verification_transcript_disclosed"] is True
    assert report["receipt_semantics_replayed"] is True
    assert report["frozen_verification_plan_replayed"] is True
    assert report["all_required_checks_passed"] is True
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    assert load_p19_verification_report(path, repository_root=tmp_path) == report


def test_echo_pass_command_cannot_satisfy_named_check(tmp_path: Path):
    plan = _active_plan(tmp_path)
    p19_path = _p19_file(tmp_path)
    p19_rel = p19_path.relative_to(tmp_path).as_posix()
    receipts = list(_receipt(tmp_path, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    forged_id = sorted(REQUIRED_CHECKS)[0]
    receipts[0] = _receipt(tmp_path, p19_rel, forged_id, forged_command=True)
    with pytest.raises(P19VerificationReportError, match="differs from frozen plan"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=_p19(),
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )


def test_inactive_plan_prevents_report_authority(tmp_path: Path):
    plan = _active_plan(tmp_path)
    import json
    doc = json.loads(plan.read_text(encoding="utf-8"))
    doc["activation_authorized"] = False
    keys = (
        "plan_generation", "frozen_pre_outcome", "activation_authorized", "verifier_entrypoint_path",
        "verifier_entrypoint_sha256", "verifier_dependency_manifest_digest", "verifier_dependencies",
        "check_contracts", "all_check_implementations_complete", "product_qualification_authorized",
    )
    doc["plan_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))
    plan.write_bytes(canonical_json_bytes(doc) + b"\n")
    p19_path = _p19_file(tmp_path)
    p19_rel = p19_path.relative_to(tmp_path).as_posix()
    receipts = tuple(_receipt(tmp_path, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    with pytest.raises(P19VerificationReportError, match="not execution-ready"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=_p19(),
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )


def test_raw_transcript_mutation_fails_report_rehash(tmp_path: Path):
    report = _build(tmp_path)
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    evidence_rel = str(report["checks"][0]["evidence_path"])
    (tmp_path / evidence_rel).write_bytes(b"mutated\n")
    with pytest.raises(Exception, match="bytes differ"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_verifier_dependency_mutation_fails_report_replay(tmp_path: Path):
    report = _build(tmp_path)
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    dependency = tmp_path / REQUIRED_IMPLEMENTATION_DEPENDENCIES[0]
    dependency.write_text("# mutated verifier dependency\n", encoding="utf-8")
    with pytest.raises(Exception, match="dependency bytes differ"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_self_consistent_report_cannot_contradict_bound_receipt_semantics(tmp_path: Path):
    report = _build(tmp_path)
    row = report["checks"][0]
    row["command_argv"] = ["python", "scripts/dgc_external_p19_verifier.py", "--check-id", str(row["check_id"]), "--p19", str(report["p19_path"]), "--evidence-output", "artifacts/dgc-product-v1/generated/forged.json"]
    row["command_sha256"] = sha256_bytes(canonical_json_bytes(row["command_argv"]))
    report["checks_digest"] = sha256_bytes(canonical_json_bytes(report["checks"]))
    path = tmp_path / "forged-report.json"
    path.write_bytes(report_bytes(report))
    with pytest.raises(Exception, match="report/receipt semantic mismatch"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_incomplete_p19_cannot_receive_green_verification_report(tmp_path: Path):
    plan, p19_path, receipts = _fixture(tmp_path)
    p19 = dict(_p19())
    p19["family_evidence_complete"] = False
    with pytest.raises(P19VerificationReportError, match="incomplete P19"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=p19,
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )
