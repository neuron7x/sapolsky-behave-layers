from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.frozen_observation_builder as runtime
from cwc.governance.frozen_observation_builder import (
    FrozenObservationBuilderError,
    build_frozen_observations,
    load_frozen_observation_builder,
)
from cwc.governance.materialization_transaction import sha256_file


def _fixture(tmp_path: Path, *, mode: str = "STATIC_ONLY_V1"):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = repo / "observations"
    root.mkdir()
    implementation = root / "builder.py"
    implementation.write_text("print('unused')\n", encoding="utf-8")
    config = root / "builder.json"
    config_doc = {
        "schema": "DGC_OBSERVATION_BUILDER_CONFIG_V1",
        "mode": mode,
        "observation_fields": ["budget_remaining", "initial_uncertainty", "step_index"],
        "probe_action_id": "STANDARD" if mode == "COMMON_MODEL_PROBE_V1" else None,
    }
    config.write_text(json.dumps(config_doc, sort_keys=True) + "\n", encoding="utf-8")
    manifest = root / "manifest.json"
    manifest_doc = {
        "schema": "DGC_OBSERVATION_BUILDER_MANIFEST_V1",
        "protocol": "DGC_OBSERVATION_BUILDER_PROTOCOL_V1",
        "request_schema": "DGC_OBSERVATION_REQUEST_V1",
        "response_schema": "DGC_OBSERVATION_RESPONSE_V1",
        "implementation_path": "observations/builder.py",
        "implementation_sha256": sha256_file(implementation),
        "config_path": "observations/builder.json",
        "config_sha256": sha256_file(config),
        "argv": [
            sys.executable,
            "observations/builder.py",
            "--config",
            "observations/builder.json",
        ],
        "timeout_seconds": 5,
        "mode": mode,
        "observation_fields": config_doc["observation_fields"],
        "probe_action_id": config_doc["probe_action_id"],
        "confirmatory_label_access": False,
        "post_outcome_feature_mutation_allowed": False,
        "network_access_allowed": mode == "COMMON_MODEL_PROBE_V1",
    }
    if mode == "COMMON_MODEL_PROBE_V1":
        manifest_doc["probe_cost_allocation"] = "CHARGED_IDENTICALLY_TO_ALL_ARMS"
        manifest_doc["probe_runs_in_clean_environment"] = True
    manifest.write_text(json.dumps(manifest_doc, sort_keys=True) + "\n", encoding="utf-8")
    execution = {
        "components": [{
            "component": "observation_builder_manifest",
            "path": "observations/manifest.json",
            "sha256": sha256_file(manifest),
        }]
    }
    return repo, implementation, config, manifest, execution


def _success_run(captured: dict):
    def run(command, **kwargs):
        captured["command"] = command
        request = json.loads(kwargs["input"].decode("utf-8"))
        captured["request"] = request
        response = {
            "schema": "DGC_OBSERVATION_RESPONSE_V1",
            "observations": {
                "budget_remaining": 1.0,
                "initial_uncertainty": 0.25,
                "step_index": 0,
            },
            "trace": {
                "builder": "fixture",
                "task_id": request["task_id"],
            },
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response, sort_keys=True).encode("utf-8"),
            stderr=b"",
        )
    return run


def test_static_builder_executes_under_network_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, execution = _fixture(tmp_path)
    captured = {}
    monkeypatch.setattr(runtime.subprocess, "run", _success_run(captured))
    result = build_frozen_observations(
        repository_root=repo,
        execution_freeze=execution,
        family_id="TERMINAL_BENCH_2_1",
        task_id="task-a",
        replicate=0,
        task_metadata={"instruction_bytes": 1200},
    )
    assert captured["command"][:3] == ["unshare", "--net", "--"]
    assert captured["request"]["task_metadata"] == {"instruction_bytes": 1200}
    assert result.observations == {
        "budget_remaining": 1.0,
        "initial_uncertainty": 0.25,
        "step_index": 0.0,
    }
    assert result.product_promotion_authorized is False
    assert len(result.request_digest) == 64
    assert len(result.response_digest) == 64


def test_common_model_probe_fails_closed_until_workload_metering_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, execution = _fixture(tmp_path, mode="COMMON_MODEL_PROBE_V1")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    with pytest.raises(
        FrozenObservationBuilderError,
        match="COMMON_MODEL_PROBE_REQUIRES_WORKLOAD_ADAPTER",
    ):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={},
        )


def test_confirmatory_outcome_metadata_is_rejected_before_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, execution = _fixture(tmp_path)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    with pytest.raises(FrozenObservationBuilderError, match="forbidden outcome fields"):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={"ground_truth": "secret"},
        )


def test_observation_response_field_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, execution = _fixture(tmp_path)

    def run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "schema": "DGC_OBSERVATION_RESPONSE_V1",
                "observations": {
                    "budget_remaining": 1.0,
                    "step_index": 0,
                },
                "trace": {"builder": "fixture"},
            }).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenObservationBuilderError, match="fields differ"):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={},
        )


def test_nonfinite_observation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, execution = _fixture(tmp_path)

    def run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "schema": "DGC_OBSERVATION_RESPONSE_V1",
                "observations": {
                    "budget_remaining": 1.0,
                    "initial_uncertainty": float("nan"),
                    "step_index": 0,
                },
                "trace": {"builder": "fixture"},
            }).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenObservationBuilderError, match="must be finite"):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={},
        )


def test_implementation_byte_drift_is_rejected_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, implementation, _, _, execution = _fixture(tmp_path)
    implementation.write_text("print('tampered')\n", encoding="utf-8")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    with pytest.raises(FrozenObservationBuilderError, match="implementation bytes differ"):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={},
        )


def test_symlinked_manifest_is_rejected(tmp_path: Path):
    repo, _, _, manifest, execution = _fixture(tmp_path)
    real = manifest.with_name("manifest-real.json")
    manifest.rename(real)
    manifest.symlink_to(real)
    with pytest.raises(FrozenObservationBuilderError, match="symlink"):
        load_frozen_observation_builder(
            repository_root=repo,
            execution_freeze=execution,
        )


def test_static_builder_network_permission_drift_is_rejected(tmp_path: Path):
    repo, _, _, manifest, execution = _fixture(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["network_access_allowed"] = True
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    execution["components"][0]["sha256"] = sha256_file(manifest)
    with pytest.raises(FrozenObservationBuilderError, match="static observation builder"):
        build_frozen_observations(
            repository_root=repo,
            execution_freeze=execution,
            family_id="TERMINAL_BENCH_2_1",
            task_id="task-a",
            replicate=0,
            task_metadata={},
        )
