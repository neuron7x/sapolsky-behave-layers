from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.frozen_observation_runtime as runtime
from cwc.governance.frozen_observation_runtime import (
    FrozenObservationRuntimeError,
    invoke_frozen_observation_provider,
)
from cwc.governance.materialization_transaction import sha256_file


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    scripts = repo / "scripts"
    scripts.mkdir()
    impl = scripts / "provider.py"
    impl.write_text("print('unused')\n", encoding="utf-8")

    manifests = repo / "manifests"
    manifests.mkdir()
    manifest = manifests / "observations.json"
    manifest_doc = {
        "schema": "DGC_OBSERVATION_PROVIDER_MANIFEST_V1",
        "protocol": "DGC_PREOUTCOME_OBSERVATION_PROTOCOL_V1",
        "request_schema": "DGC_PREOUTCOME_OBSERVATION_REQUEST_V1",
        "response_schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
        "implementation_path": "scripts/provider.py",
        "implementation_sha256": sha256_file(impl),
        "argv": [sys.executable, "scripts/provider.py"],
        "timeout_seconds": 5,
        "output_fields": ["budget_remaining", "step_index"],
        "network_access_allowed": False,
        "confirmatory_label_access": False,
        "post_outcome_access_allowed": False,
    }
    manifest.write_text(json.dumps(manifest_doc, sort_keys=True) + "\n", encoding="utf-8")
    execution = {
        "components": [{
            "component": "observation_provider_manifest",
            "path": "manifests/observations.json",
            "sha256": sha256_file(manifest),
            "bytes": manifest.stat().st_size,
            "schema": "DGC_OBSERVATION_PROVIDER_MANIFEST_V1",
        }]
    }
    materialization = tmp_path / "materialization"
    materialization.mkdir()
    return repo, impl, manifest, execution, materialization


def _run_success(captured: dict):
    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        req = json.loads(kwargs["input"].decode("utf-8"))
        response = {
            "schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
            "family_id": req["family_id"],
            "task_id": req["task_id"],
            "observations": {
                "budget_remaining": req["budget_remaining"],
                "step_index": req["step_index"],
            },
            "output_fields": ["budget_remaining", "step_index"],
            "source_manifest_digest": "a" * 64,
            "confirmatory_label_access": False,
            "post_outcome_access": False,
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response, sort_keys=True).encode("utf-8"),
            stderr=b"",
        )
    return run


def test_runtime_executes_provider_under_network_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, execution, materialization = _fixture(tmp_path)
    captured = {}
    monkeypatch.setattr(runtime.subprocess, "run", _run_success(captured))
    result = invoke_frozen_observation_provider(
        repository_root=repo,
        execution_freeze=execution,
        materialization_root=materialization,
        family_id="TERMINAL_BENCH_2_1",
        task_id="task-a",
        budget_remaining=1.5,
        step_index=0,
    )
    assert captured["command"][:3] == ["unshare", "--net", "--"]
    assert result.observations == {"budget_remaining": 1.5, "step_index": 0}
    assert result.output_fields == ("budget_remaining", "step_index")
    assert result.source_manifest_digest == "a" * 64
    assert len(result.request_digest) == 64
    assert len(result.response_digest) == 64


def test_implementation_byte_drift_is_rejected_before_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, impl, _, execution, materialization = _fixture(tmp_path)
    impl.write_text("print('tampered')\n", encoding="utf-8")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(FrozenObservationRuntimeError, match="implementation bytes differ"):
        invoke_frozen_observation_provider(
            repository_root=repo,
            execution_freeze=execution,
            materialization_root=materialization,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            budget_remaining=1.0,
            step_index=0,
        )


def test_extra_response_field_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, execution, materialization = _fixture(tmp_path)

    def run(command, **kwargs):
        req = json.loads(kwargs["input"].decode("utf-8"))
        response = {
            "schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
            "family_id": req["family_id"],
            "task_id": req["task_id"],
            "observations": {
                "budget_remaining": 1.0,
                "ground_truth": 1,
                "step_index": 0,
            },
            "output_fields": ["budget_remaining", "step_index"],
            "source_manifest_digest": "b" * 64,
            "confirmatory_label_access": False,
            "post_outcome_access": False,
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode(), stderr=b"")

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenObservationRuntimeError, match="fields differ"):
        invoke_frozen_observation_provider(
            repository_root=repo,
            execution_freeze=execution,
            materialization_root=materialization,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            budget_remaining=1.0,
            step_index=0,
        )


def test_response_identity_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, execution, materialization = _fixture(tmp_path)

    def run(command, **kwargs):
        response = {
            "schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
            "family_id": "SWE_BENCH_VERIFIED",
            "task_id": "other",
            "observations": {"budget_remaining": 1.0, "step_index": 0},
            "output_fields": ["budget_remaining", "step_index"],
            "source_manifest_digest": "c" * 64,
            "confirmatory_label_access": False,
            "post_outcome_access": False,
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode(), stderr=b"")

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenObservationRuntimeError, match="identity mismatch"):
        invoke_frozen_observation_provider(
            repository_root=repo,
            execution_freeze=execution,
            materialization_root=materialization,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            budget_remaining=1.0,
            step_index=0,
        )


def test_illegal_label_access_claim_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, execution, materialization = _fixture(tmp_path)

    def run(command, **kwargs):
        req = json.loads(kwargs["input"].decode("utf-8"))
        response = {
            "schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
            "family_id": req["family_id"],
            "task_id": req["task_id"],
            "observations": {"budget_remaining": 1.0, "step_index": 0},
            "output_fields": ["budget_remaining", "step_index"],
            "source_manifest_digest": "d" * 64,
            "confirmatory_label_access": True,
            "post_outcome_access": False,
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode(), stderr=b"")

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenObservationRuntimeError, match="illegally claims label access"):
        invoke_frozen_observation_provider(
            repository_root=repo,
            execution_freeze=execution,
            materialization_root=materialization,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            budget_remaining=1.0,
            step_index=0,
        )


def test_missing_network_isolator_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, execution, materialization = _fixture(tmp_path)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(OSError("unshare unavailable")),
    )
    with pytest.raises(FrozenObservationRuntimeError, match="could not start with network isolation"):
        invoke_frozen_observation_provider(
            repository_root=repo,
            execution_freeze=execution,
            materialization_root=materialization,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            budget_remaining=1.0,
            step_index=0,
        )
