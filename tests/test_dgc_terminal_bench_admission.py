from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.terminal_bench_admission import (
    TerminalBenchAdmissionError,
    admit_terminal_bench_trial,
)


def _write_trial(root: Path, *, task: str = "task-a", reward=1.0, cost=0.25) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    result = {
        "task_name": task,
        "trial_name": "trial-1",
        "verifier_result": {"rewards": {"reward": reward}},
        "agent_result": {
            "n_input_tokens": 100,
            "n_cache_tokens": 20,
            "n_output_tokens": 40,
            "cost_usd": cost,
        },
        "agent_info": {
            "model_info": {
                "provider": "provider-x",
                "name": "model-y",
            }
        },
    }
    (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
    trajectory = root / "agent" / "trajectory.json"
    trajectory.parent.mkdir()
    trajectory.write_text(json.dumps({"messages": [{"role": "assistant", "content": "ok"}]}), encoding="utf-8")
    return root


def test_admission_binds_upstream_reward_usage_and_raw_evidence(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    admitted = admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")
    assert admitted.quality == pytest.approx(1.0)
    assert admitted.agent_metered_cost_usd == pytest.approx(0.25)
    assert admitted.n_input_tokens == 100
    assert admitted.n_cache_tokens == 20
    assert admitted.n_output_tokens == 40
    assert admitted.provider == "provider-x"
    assert admitted.model == "model-y"
    assert len(admitted.result_sha256) == 64
    assert len(admitted.trajectory_sha256) == 64
    assert len(admitted.evidence_digest) == 64
    assert admitted.physical_cost_authority is False
    assert admitted.provider_live_authority is False
    assert admitted.product_promotion_authorized is False


def test_task_substitution_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial", task="task-b")
    with pytest.raises(TerminalBenchAdmissionError, match="task identity"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_missing_upstream_reward_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    result_path = root / "result.json"
    doc = json.loads(result_path.read_text())
    doc["verifier_result"] = {"rewards": {}}
    result_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TerminalBenchAdmissionError, match="rewards missing"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_ambiguous_multi_reward_without_primary_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    result_path = root / "result.json"
    doc = json.loads(result_path.read_text())
    doc["verifier_result"] = {"rewards": {"a": 1.0, "b": 0.0}}
    result_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TerminalBenchAdmissionError, match="explicit upstream primary reward"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_missing_metered_cost_is_rejected_not_zero_filled(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    result_path = root / "result.json"
    doc = json.loads(result_path.read_text())
    doc["agent_result"]["cost_usd"] = None
    result_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TerminalBenchAdmissionError, match="cost_usd"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_invalid_cache_accounting_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    result_path = root / "result.json"
    doc = json.loads(result_path.read_text())
    doc["agent_result"]["n_cache_tokens"] = 101
    result_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TerminalBenchAdmissionError, match="cannot exceed"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_symlinked_result_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    result = root / "result.json"
    real = root / "result-real.json"
    result.rename(real)
    result.symlink_to(real)
    with pytest.raises(TerminalBenchAdmissionError, match="symlink evidence path rejected"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_symlinked_parent_component_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial")
    agent = root / "agent"
    real = root / "agent-real"
    agent.rename(real)
    agent.symlink_to(real, target_is_directory=True)
    with pytest.raises(TerminalBenchAdmissionError, match="symlink evidence path rejected"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")


def test_out_of_range_reward_is_rejected(tmp_path: Path):
    root = _write_trial(tmp_path / "trial", reward=1.5)
    with pytest.raises(TerminalBenchAdmissionError, match=r"\[0,1\]"):
        admit_terminal_bench_trial(trial_root=root, expected_task_id="task-a")
