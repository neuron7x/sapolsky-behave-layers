from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.real_transfer_01.contract import ContractError
from experiments.real_transfer_01.evaluator import REQUIRED_POLICIES
from experiments.real_transfer_01.readiness import analyze, validate_runtime_binding


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_sha(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _runtime_manifest(root: Path) -> dict:
    runner = root / "runner.py"
    runner.write_text("RUNNER_VERSION = 'test'\n", encoding="utf-8")
    decoding = {"temperature": 0}
    policy_bindings = {}
    for policy in REQUIRED_POLICIES:
        path = root / f"policy_{policy.lower()}.py"
        path.write_text(f"POLICY = {policy!r}\n", encoding="utf-8")
        policy_bindings[policy] = {
            "path": path.name,
            "sha256": _sha_bytes(path.read_bytes()),
        }
    manifest = {
        "runner_version": "test",
        "runner_path": "runner.py",
        "runner_sha256": _sha_bytes(runner.read_bytes()),
        "weights_sha256": _sha_bytes(b"weights"),
        "tokenizer_sha256": _sha_bytes(b"tokenizer"),
        "prompt_template_sha256": _sha_bytes(b"prompt"),
        "decoding_parameters": decoding,
        "decoding_parameters_sha256": _json_sha(decoding),
        "calibration_procedure_sha256": _sha_bytes(b"calibration"),
        "governor_parameters_sha256": _sha_bytes(b"governor"),
        "training_corpus_provenance": "UNKNOWN",
        "policies": list(REQUIRED_POLICIES),
        "policy_implementations": policy_bindings,
        "calibration_binding": {
            "threshold_fit_cohort": "CALIBRATION",
            "observed_cohorts_before_freeze": [],
        },
    }
    return manifest


def test_runtime_binding_requires_runner_and_all_comparator_hashes(tmp_path: Path) -> None:
    good = _runtime_manifest(tmp_path)
    validate_runtime_binding(good, root=tmp_path)

    missing = dict(good)
    missing["policy_implementations"] = dict(good["policy_implementations"])
    del missing["policy_implementations"]["MODEL_ID_MAXIMIN"]
    with pytest.raises(ContractError):
        validate_runtime_binding(missing, root=tmp_path)

    drift = dict(good)
    drift["policy_implementations"] = {k: dict(v) for k, v in good["policy_implementations"].items()}
    changed = tmp_path / drift["policy_implementations"]["MAX_SCORE_MARGIN"]["path"]
    changed.write_text("MUTATED = True\n", encoding="utf-8")
    with pytest.raises(ContractError):
        validate_runtime_binding(drift, root=tmp_path)

    # restore the file so the next independent mutation starts from a valid manifest
    restored = _runtime_manifest(tmp_path)
    tuned = dict(restored)
    tuned["calibration_binding"] = {
        "threshold_fit_cohort": "PRIMARY",
        "observed_cohorts_before_freeze": ["PRIMARY"],
    }
    with pytest.raises(ContractError):
        validate_runtime_binding(tuned, root=tmp_path)


def test_current_repository_readiness_fails_closed_as_not_tested() -> None:
    result = analyze()
    assert result["execution_status"] == "NOT_TESTED"
    assert result["scientific_verdict"] == "NOT_TESTED"
    assert result["checks"]["temporal_gate"] == "PASS"
    assert result["checks"]["semantic_mutations"] == {"killed": 13, "total": 13}
    assert any(x.startswith("SOURCE_MANIFEST_MISSING:") for x in result["blockers"])
    assert any(x.startswith("MODEL_MANIFEST_MISSING:") for x in result["blockers"])
