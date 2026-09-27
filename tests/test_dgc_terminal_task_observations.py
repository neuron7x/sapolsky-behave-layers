from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.terminal_task_observations import (
    OBSERVATION_FIELDS,
    TerminalObservationError,
    extract_terminal_task_observations,
)


def _task(root: Path, name: str = "task-a") -> Path:
    task = root / name
    (task / "environment" / "sub").mkdir(parents=True)
    (task / "instruction.md").write_text("solve this task\n", encoding="utf-8")
    (task / "task.toml").write_text("[task]\nname='task-a'\n", encoding="utf-8")
    (task / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    (task / "environment" / "sub" / "setup.sh").write_text("echo setup\n", encoding="utf-8")
    (task / "solution").mkdir()
    (task / "solution" / "answer.sh").write_text("echo secret\n", encoding="utf-8")
    (task / "tests").mkdir()
    (task / "tests" / "test.sh").write_text("exit 0\n", encoding="utf-8")
    return task


def test_extracts_only_preoutcome_metadata(tmp_path: Path):
    task = _task(tmp_path)
    observed = extract_terminal_task_observations(
        task_root=task,
        task_id="task-a",
        budget_remaining=2.5,
        step_index=0,
    )
    assert tuple(sorted(observed.observations)) == OBSERVATION_FIELDS
    assert observed.observations["budget_remaining"] == pytest.approx(2.5)
    assert observed.observations["step_index"] == 0
    assert observed.observations["environment_file_count"] == 2
    assert observed.observations["instruction_bytes"] == len("solve this task\n".encode())
    assert observed.observations["task_config_bytes"] == len("[task]\nname='task-a'\n".encode())
    assert len(observed.source_manifest_digest) == 64


def test_solution_and_tests_are_not_observation_inputs(tmp_path: Path):
    task = _task(tmp_path)
    first = extract_terminal_task_observations(
        task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
    )
    (task / "solution" / "answer.sh").write_text("completely different secret\n", encoding="utf-8")
    (task / "tests" / "test.sh").write_text("exit 99\n", encoding="utf-8")
    second = extract_terminal_task_observations(
        task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
    )
    assert second.observations == first.observations
    assert second.source_manifest_digest == first.source_manifest_digest


def test_instruction_change_changes_preoutcome_identity(tmp_path: Path):
    task = _task(tmp_path)
    first = extract_terminal_task_observations(
        task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
    )
    (task / "instruction.md").write_text("different visible instruction\n", encoding="utf-8")
    second = extract_terminal_task_observations(
        task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
    )
    assert second.source_manifest_digest != first.source_manifest_digest
    assert second.observations["instruction_bytes"] != first.observations["instruction_bytes"]


def test_environment_symlink_is_rejected(tmp_path: Path):
    task = _task(tmp_path)
    target = task / "environment" / "real.txt"
    target.write_text("x", encoding="utf-8")
    (task / "environment" / "alias.txt").symlink_to(target)
    with pytest.raises(TerminalObservationError, match="environment symlink rejected"):
        extract_terminal_task_observations(
            task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
        )


def test_task_identity_substitution_is_rejected(tmp_path: Path):
    task = _task(tmp_path, name="task-b")
    with pytest.raises(TerminalObservationError, match="task id/path binding mismatch"):
        extract_terminal_task_observations(
            task_root=task, task_id="task-a", budget_remaining=1.0, step_index=0
        )


@pytest.mark.parametrize("budget", [-1, float("nan"), float("inf")])
def test_invalid_budget_is_rejected(tmp_path: Path, budget: float):
    task = _task(tmp_path)
    with pytest.raises(TerminalObservationError, match="budget_remaining"):
        extract_terminal_task_observations(
            task_root=task, task_id="task-a", budget_remaining=budget, step_index=0
        )


def test_negative_step_is_rejected(tmp_path: Path):
    task = _task(tmp_path)
    with pytest.raises(TerminalObservationError, match="step_index"):
        extract_terminal_task_observations(
            task_root=task, task_id="task-a", budget_remaining=1.0, step_index=-1
        )
