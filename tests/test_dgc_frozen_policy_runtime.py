from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.frozen_policy_runtime as runtime
from cwc.governance.execution_manifest_freeze import (
    policy_action_catalog_digest,
    policy_observation_contract_digest,
)
from cwc.governance.frozen_policy_runtime import (
    FrozenPolicyRuntimeError,
    invoke_frozen_policy,
)
from cwc.governance.materialization_transaction import sha256_file


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    policies = repo / "policies"
    policies.mkdir()
    implementation = policies / "B0.py"
    implementation.write_text("print('unused')\n", encoding="utf-8")
    config = policies / "B0.config.json"
    config_doc = {
        "schema": "DGC_GOVERNANCE_POLICY_CONFIG_V1",
        "policy_id": "B0",
        "action_ids": ["DEEP", "STANDARD"],
        "observation_fields": ["budget_remaining", "initial_uncertainty", "step_index"],
    }
    config.write_text(json.dumps(config_doc, sort_keys=True) + "\n", encoding="utf-8")
    manifest = policies / "B0.manifest.json"
    manifest_doc = {
        "schema": "DGC_GOVERNANCE_POLICY_MANIFEST_V1",
        "policy_id": "B0",
        "protocol": "DGC_GOVERNANCE_POLICY_EXECUTION_PROTOCOL_V1",
        "request_schema": "DGC_POLICY_DECISION_REQUEST_V1",
        "response_schema": "DGC_POLICY_DECISION_RESPONSE_V1",
        "state_protocol": "STATE_IN_REQUEST_ONLY",
        "network_access_allowed": False,
        "confirmatory_label_access": False,
        "implementation_path": "policies/B0.py",
        "implementation_sha256": sha256_file(implementation),
        "config_path": "policies/B0.config.json",
        "config_sha256": sha256_file(config),
        "argv": [
            sys.executable,
            "policies/B0.py",
            "--config",
            "policies/B0.config.json",
        ],
        "timeout_seconds": 5,
        "action_catalog_digest": policy_action_catalog_digest(config_doc["action_ids"]),
        "observation_contract_digest": policy_observation_contract_digest(
            config_doc["observation_fields"]
        ),
    }
    manifest.write_text(json.dumps(manifest_doc, sort_keys=True) + "\n", encoding="utf-8")
    frozen = {
        "policy_id": "B0",
        "path": "policies/B0.manifest.json",
        "sha256": sha256_file(manifest),
        "implementation_path": "policies/B0.py",
        "implementation_sha256": sha256_file(implementation),
        "config_path": "policies/B0.config.json",
        "config_sha256": sha256_file(config),
        "protocol": manifest_doc["protocol"],
        "argv": manifest_doc["argv"],
        "timeout_seconds": manifest_doc["timeout_seconds"],
        "action_catalog_digest": manifest_doc["action_catalog_digest"],
        "observation_contract_digest": manifest_doc["observation_contract_digest"],
    }
    observations = {
        "budget_remaining": 1.0,
        "initial_uncertainty": 0.25,
        "step_index": 0,
    }
    return repo, implementation, config, manifest, frozen, observations


def _success_run(captured: dict):
    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        req = json.loads(kwargs["input"].decode("utf-8"))
        response = {
            "schema": "DGC_POLICY_DECISION_RESPONSE_V1",
            "policy_id": req["policy_id"],
            "action_id": "STANDARD",
            "next_state": {"calls": 1},
            "trace": {
                "observation_digest": req["observation_contract_digest"],
                "decision": "STANDARD",
            },
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response, sort_keys=True).encode("utf-8"),
            stderr=b"",
        )
    return run


def test_policy_executes_under_linux_network_namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)
    captured = {}
    monkeypatch.setattr(runtime.subprocess, "run", _success_run(captured))
    decision = invoke_frozen_policy(
        repository_root=repo,
        frozen_policy=frozen,
        task_id="task-1",
        replicate=0,
        observations=observations,
        state={},
    )
    assert captured["command"][:3] == ["unshare", "--net", "--"]
    assert captured["command"][3:] == frozen["argv"]
    request = json.loads(captured["kwargs"]["input"].decode("utf-8"))
    assert request["schema"] == "DGC_POLICY_DECISION_REQUEST_V1"
    assert request["observations"] == observations
    assert request["state"] == {}
    assert decision.action_id == "STANDARD"
    assert decision.next_state == {"calls": 1}
    assert decision.network_isolation == "LINUX_UNSHARE_NET_V1"
    assert len(decision.request_digest) == 64
    assert len(decision.response_digest) == 64


def test_extra_observation_is_rejected_before_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    observations["ground_truth"] = 1
    with pytest.raises(FrozenPolicyRuntimeError, match="must equal frozen contract"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )


def test_missing_observation_is_rejected_before_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    observations.pop("initial_uncertainty")
    with pytest.raises(FrozenPolicyRuntimeError, match="must equal frozen contract"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )


def test_action_outside_frozen_catalog_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)

    def run(command, **kwargs):
        req = json.loads(kwargs["input"].decode("utf-8"))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "schema": "DGC_POLICY_DECISION_RESPONSE_V1",
                "policy_id": req["policy_id"],
                "action_id": "ULTRA",
                "next_state": {},
                "trace": {"decision": "ULTRA"},
            }).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(FrozenPolicyRuntimeError, match="outside frozen catalog"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )


def test_policy_byte_drift_is_rejected_before_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, implementation, _, _, frozen, observations = _fixture(tmp_path)
    implementation.write_text("print('tampered')\n", encoding="utf-8")
    monkeypatch.setattr(runtime.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run"))
    with pytest.raises(FrozenPolicyRuntimeError, match="implementation bytes differ"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )


def test_network_isolator_start_failure_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("unshare unavailable")

    monkeypatch.setattr(runtime.subprocess, "run", fail)
    with pytest.raises(FrozenPolicyRuntimeError, match="could not start with network isolation"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )


def test_nonzero_policy_exit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, _, _, frozen, observations = _fixture(tmp_path)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=17, stdout=b"", stderr=b"boom"),
    )
    with pytest.raises(FrozenPolicyRuntimeError, match="exited nonzero"):
        invoke_frozen_policy(
            repository_root=repo,
            frozen_policy=frozen,
            task_id="task-1",
            replicate=0,
            observations=observations,
        )
