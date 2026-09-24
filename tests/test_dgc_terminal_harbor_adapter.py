from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.terminal_harbor_adapter as adapter
from cwc.governance.materialization_transaction import sha256_file
from cwc.governance.terminal_harbor_adapter import (
    TerminalHarborAdapterError,
    execute_terminal_harbor_unit,
)


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifests = repo / "manifests"
    manifests.mkdir()
    budget = manifests / "budget.json"
    budget.write_text(
        json.dumps({
            "schema": "DGC_BUDGET_MANIFEST_V1",
            "max_tokens": 10000,
            "max_cost_usd": 2.0,
            "max_wall_time_s": 60,
            "max_steps": 10,
        }),
        encoding="utf-8",
    )
    materialization = tmp_path / "materialization"
    task = materialization / "TERMINAL_BENCH_2_1" / "repo" / "tasks" / "task-a"
    task.mkdir(parents=True)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    unit_root = tmp_path / "unit"
    unit_root.mkdir()
    request = {
        "schema": "DGC_UNIT_EXECUTION_REQUEST_V1",
        "family_id": "TERMINAL_BENCH_2_1",
        "generation_id": "gen-1",
        "unit": {"task_id": "task-a", "policy_id": "B0", "replicate": 0},
        "attempt": 1,
        "frozen_components": [{
            "component": "budget",
            "path": "manifests/budget.json",
            "sha256": sha256_file(budget),
            "bytes": budget.stat().st_size,
            "schema": "DGC_BUDGET_MANIFEST_V1",
        }],
        "governance_policy": {"policy_id": "B0"},
    }
    return repo, materialization, runtime, unit_root, request


def _patch_stack(monkeypatch: pytest.MonkeyPatch, runtime_root: Path):
    monkeypatch.setattr(
        adapter,
        "verify_benchmark_runtime",
        lambda **kwargs: SimpleNamespace(
            runtime_name="harbor",
            runtime_root=str(runtime_root),
            invocation=("uv", "run", "--frozen", "harbor"),
            document={"runtime_name": "harbor", "repository_commit": "1" * 40},
        ),
    )
    monkeypatch.setattr(
        adapter,
        "invoke_frozen_observation_provider",
        lambda **kwargs: SimpleNamespace(
            observations={
                "budget_remaining": 2.0,
                "environment_file_count": 1,
                "environment_total_bytes": 10,
                "instruction_bytes": 20,
                "step_index": 0,
                "task_config_bytes": 30,
            },
            document={"source_manifest_digest": "a" * 64},
        ),
    )
    monkeypatch.setattr(
        adapter,
        "invoke_frozen_policy",
        lambda **kwargs: SimpleNamespace(
            action_id="STANDARD",
            document={"action_id": "STANDARD", "request_digest": "b" * 64},
        ),
    )
    action = SimpleNamespace(
        action_id="STANDARD",
        harbor_agent="agent-standard",
        harbor_agent_argument="acp:agent-standard@1.0.0",
        harbor_model_argument="provider/model",
        agent_version="1.0.0",
        provider="provider",
        model_id="model",
        model_version="v1",
    )
    monkeypatch.setattr(
        adapter,
        "load_frozen_action_catalog",
        lambda **kwargs: SimpleNamespace(resolve=lambda action_id: action),
    )
    return action


def _write_harbor_trial(
    command: list[str],
    *,
    metadata: dict | None = None,
    model_name: str = "model",
    provider_call_id: str | None = "req-1",
):
    jobs_dir = Path(command[command.index("--jobs-dir") + 1])
    job_name = command[command.index("--job-name") + 1]
    trial = jobs_dir / job_name / "trial-1"
    (trial / "agent").mkdir(parents=True)
    traces = [{
        "trace_id": "trace-1",
        "decision_id": "task-a::B0::0",
        "policy_id": "B0",
        "authority": "PROVIDER_LIVE",
        "provider": "provider",
        "model": "model",
        "model_version": "v1",
        "rate_card_digest": "c" * 64,
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "cache_write_tokens": 0,
        "long_cache_write_tokens": 0,
        "output_tokens": 10,
        "provider_call_id": provider_call_id,
        "provider_call_id_kind": "PROVIDER_RESPONSE_ID",
    }]
    if metadata is None:
        metadata = {
            "dgc_provider_usage_traces": traces,
            "dgc_physical_cost_evidence": {
                "router_usd": {
                    "value_usd": 0.0,
                    "authority": "ZERO_BY_CONTRACT",
                    "source_digest": "d" * 64,
                }
            },
        }
    result = {
        "task_name": "task-a",
        "trial_name": "trial-1",
        "verifier_result": {"rewards": {"reward": 1.0}},
        "agent_result": {
            "n_input_tokens": 100,
            "n_cache_tokens": 20,
            "n_output_tokens": 10,
            "cost_usd": 0.1,
            "metadata": metadata,
        },
        "agent_info": {
            "name": "agent-standard",
            "version": "1.0.0",
            "model_info": {"provider": "provider", "name": model_name},
        },
    }
    (trial / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps({"messages": [{"role": "assistant", "content": "done"}]}),
        encoding="utf-8",
    )


def test_adapter_executes_exact_frozen_harbor_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)
    captured = {}

    def run(command, **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = kwargs
        _write_harbor_trial(list(command))
        return SimpleNamespace(returncode=0, stdout=b"harbor-ok", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    response = execute_terminal_harbor_unit(
        request=request,
        repository_root=repo,
        materialization_root=materialization,
        runtime_root=runtime_root,
        unit_runtime_root=unit_root,
    )
    command = captured["command"]
    assert command[:5] == ["uv", "run", "--frozen", "harbor", "run"]
    assert command[command.index("--agent") + 1] == "acp:agent-standard@1.0.0"
    assert command[command.index("--model") + 1] == "provider/model"
    assert command[command.index("--n-attempts") + 1] == "1"
    assert command[command.index("--n-concurrent") + 1] == "1"
    assert command[command.index("--max-retries") + 1] == "0"
    assert response["schema"] == "DGC_UNIT_EXECUTION_RESPONSE_V1"
    assert response["quality"] == pytest.approx(1.0)
    assert response["unit"] == request["unit"]
    assert response["provider_usage_traces"][0]["provider_call_id"] == "req-1"
    assert response["provider_usage_traces"][0]["provider_call_id_kind"] == "PROVIDER_RESPONSE_ID"
    assert response["trace"]["action"]["action_id"] == "STANDARD"
    assert len(response["trace"]["harbor_command_digest"]) == 64


def test_missing_dgc_agent_metadata_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)

    def run(command, **kwargs):
        _write_harbor_trial(list(command), metadata={})
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    with pytest.raises(TerminalHarborAdapterError, match="provider_usage_traces"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )


def test_missing_real_provider_call_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)

    def run(command, **kwargs):
        _write_harbor_trial(list(command), provider_call_id=None)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    with pytest.raises(TerminalHarborAdapterError, match="real provider_call_id"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )


def test_untyped_provider_call_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)

    def run(command, **kwargs):
        _write_harbor_trial(list(command))
        jobs_dir = Path(command[command.index("--jobs-dir") + 1])
        job_name = command[command.index("--job-name") + 1]
        result_path = next(
            p / "result.json"
            for p in (jobs_dir / job_name).iterdir()
            if p.is_dir()
        )
        doc = json.loads(result_path.read_text())
        del doc["agent_result"]["metadata"]["dgc_provider_usage_traces"][0]["provider_call_id_kind"]
        result_path.write_text(json.dumps(doc), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    with pytest.raises(TerminalHarborAdapterError, match="trusted provider_call_id_kind"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )


def test_executed_model_identity_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)

    def run(command, **kwargs):
        _write_harbor_trial(list(command), model_name="other-model")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    with pytest.raises(TerminalHarborAdapterError, match="model differs"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )


def test_missing_physical_cost_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)

    def run(command, **kwargs):
        _write_harbor_trial(
            list(command),
            metadata={
                "dgc_provider_usage_traces": [{
                    "trace_id": "trace-1",
                    "decision_id": "task-a::B0::0",
                    "policy_id": "B0",
                    "authority": "PROVIDER_LIVE",
                    "provider": "provider",
                    "model": "model",
                    "model_version": "v1",
                    "rate_card_digest": "c" * 64,
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "provider_call_id": "req-1",
                }]
            },
        )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    with pytest.raises(TerminalHarborAdapterError, match="physical_cost_evidence"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )


def test_harbor_nonzero_exit_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, materialization, runtime_root, unit_root, request = _fixture(tmp_path)
    _patch_stack(monkeypatch, runtime_root)
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=9, stdout=b"", stderr=b"bad"),
    )
    with pytest.raises(TerminalHarborAdapterError, match="exited nonzero"):
        execute_terminal_harbor_unit(
            request=request,
            repository_root=repo,
            materialization_root=materialization,
            runtime_root=runtime_root,
            unit_runtime_root=unit_root,
        )
