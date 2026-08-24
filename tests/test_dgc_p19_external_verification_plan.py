from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_plan import (
    REQUIRED_IMPLEMENTATION_DEPENDENCIES,
    SCHEMA,
    P19ExternalVerificationPlanError,
    load_p19_external_verification_plan,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


def _doc(root: Path, *, active: bool, implemented: bool = True) -> dict[str, object]:
    entry = root / "scripts/dgc_external_p19_verifier.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('verifier')\n", encoding="utf-8")
    dependency_rows = []
    for rel in REQUIRED_IMPLEMENTATION_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# replay engine\n", encoding="utf-8")
        dependency_rows.append({"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    status = "IMPLEMENTED" if implemented else "NOT_IMPLEMENTED"
    rows = []
    for check_id in sorted(REQUIRED_CHECKS):
        rows.append({
            "check_id": check_id,
            "method_id": f"DGC_P19_EXTERNAL_{check_id}_V1",
            "command_template": [
                "python", "scripts/dgc_external_p19_verifier.py", "--check-id", check_id,
                "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
            ],
            "implementation_status": status,
        })
    payload = {
        "plan_generation": "TEST_PRE_OUTCOME_PLAN",
        "frozen_pre_outcome": True,
        "activation_authorized": active,
        "verifier_entrypoint_path": "scripts/dgc_external_p19_verifier.py",
        "verifier_entrypoint_sha256": sha256_file(entry),
        "verifier_dependency_manifest_digest": sha256_bytes(canonical_json_bytes(dependency_rows)),
        "verifier_dependencies": dependency_rows,
        "check_contracts": rows,
        "all_check_implementations_complete": implemented,
        "product_qualification_authorized": False,
    }
    return {"schema": SCHEMA, **payload, "plan_digest": sha256_bytes(canonical_json_bytes(payload))}


def _write(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def test_active_complete_plan_loads_and_is_content_addressed(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _doc(tmp_path, active=True, implemented=True)
    _write(path, doc)
    plan = load_p19_external_verification_plan(path, repository_root=tmp_path)
    assert plan.activation_authorized is True
    assert plan.all_check_implementations_complete is True
    assert plan.plan_digest == doc["plan_digest"]
    assert len(plan.verifier_dependencies) == len(REQUIRED_IMPLEMENTATION_DEPENDENCIES)


def test_inactive_plan_is_valid_preregistration_but_not_executable(tmp_path: Path):
    path = tmp_path / "plan.json"
    _write(path, _doc(tmp_path, active=False, implemented=False))
    plan = load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)
    assert plan.activation_authorized is False
    with pytest.raises(P19ExternalVerificationPlanError, match="not activated"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=True)


def test_activation_with_unimplemented_checks_fails_closed(tmp_path: Path):
    path = tmp_path / "plan.json"
    _write(path, _doc(tmp_path, active=True, implemented=False))
    with pytest.raises(P19ExternalVerificationPlanError, match="cannot activate"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_verifier_entrypoint_mutation_breaks_frozen_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    _write(path, _doc(tmp_path, active=True, implemented=True))
    (tmp_path / "scripts/dgc_external_p19_verifier.py").write_text("print('mutated')\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerificationPlanError, match="entrypoint bytes differ"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_verifier_dependency_mutation_breaks_frozen_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    _write(path, _doc(tmp_path, active=True, implemented=True))
    dependency = tmp_path / REQUIRED_IMPLEMENTATION_DEPENDENCIES[0]
    dependency.write_text("# mutated replay engine\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerificationPlanError, match="dependency bytes differ"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_command_template_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _doc(tmp_path, active=True, implemented=True)
    doc["check_contracts"][0]["command_template"] = ["echo", "PASS"]
    payload_keys = (
        "plan_generation", "frozen_pre_outcome", "activation_authorized",
        "verifier_entrypoint_path", "verifier_entrypoint_sha256",
        "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
        "all_check_implementations_complete", "product_qualification_authorized",
    )
    doc["plan_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in payload_keys}))
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="command template mismatch"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)
