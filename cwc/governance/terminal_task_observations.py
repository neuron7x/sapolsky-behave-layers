from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes

OBSERVATION_FIELDS = (
    "budget_remaining",
    "environment_file_count",
    "environment_total_bytes",
    "instruction_bytes",
    "step_index",
    "task_config_bytes",
)


class TerminalObservationError(RuntimeError):
    pass


def _regular_file(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise TerminalObservationError(f"{label} symlink rejected")
    if not path.is_file():
        raise TerminalObservationError(f"{label} missing regular file")
    return path


def _real_directory(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise TerminalObservationError(f"{label} symlink rejected")
    if not path.is_dir():
        raise TerminalObservationError(f"{label} missing directory")
    return path


def _finite_nonnegative(name: str, value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TerminalObservationError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise TerminalObservationError(f"{name} must be finite and >= 0")
    return parsed


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise TerminalObservationError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TerminalObservationError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise TerminalObservationError(f"{name} must be >= 0")
    return parsed


def _environment_manifest(root: Path) -> tuple[tuple[dict[str, object], ...], int]:
    rows: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root)
        current = root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise TerminalObservationError(
                    f"environment symlink rejected: {rel.as_posix()}"
                )
        if path.is_dir():
            continue
        if not path.is_file():
            raise TerminalObservationError(
                f"unsupported environment object: {rel.as_posix()}"
            )
        size = path.stat().st_size
        total += size
        rows.append({"path": rel.as_posix(), "bytes": size})
    return tuple(rows), total


@dataclass(frozen=True, slots=True)
class TerminalTaskObservations:
    task_id: str
    observations: dict[str, object]
    source_manifest_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "observations": self.observations,
            "source_manifest_digest": self.source_manifest_digest,
            "confirmatory_label_access": False,
            "post_outcome_access": False,
        }


def extract_terminal_task_observations(
    *,
    task_root: Path,
    task_id: str,
    budget_remaining: object,
    step_index: object,
) -> TerminalTaskObservations:
    supplied = Path(task_root)
    if supplied.is_symlink():
        raise TerminalObservationError("task root symlink rejected")
    root = supplied.resolve()
    if not root.is_dir():
        raise TerminalObservationError("task root missing")
    task = str(task_id).strip()
    if not task or root.name != task:
        raise TerminalObservationError("task id/path binding mismatch")

    instruction = _regular_file(root / "instruction.md", label="instruction.md")
    config = _regular_file(root / "task.toml", label="task.toml")
    environment = _real_directory(root / "environment", label="environment")
    env_rows, env_total = _environment_manifest(environment)

    observations = {
        "budget_remaining": _finite_nonnegative("budget_remaining", budget_remaining),
        "environment_file_count": len(env_rows),
        "environment_total_bytes": env_total,
        "instruction_bytes": instruction.stat().st_size,
        "step_index": _nonnegative_int("step_index", step_index),
        "task_config_bytes": config.stat().st_size,
    }
    if tuple(sorted(observations)) != OBSERVATION_FIELDS:
        raise TerminalObservationError("internal observation field contract drift")

    source_manifest = {
        "task_id": task,
        "instruction": {"path": "instruction.md", "bytes": instruction.stat().st_size},
        "task_config": {"path": "task.toml", "bytes": config.stat().st_size},
        "environment": list(env_rows),
        "excluded_paths": ["solution", "tests"],
    }
    digest = hashlib.sha256(canonical_json_bytes(source_manifest)).hexdigest()
    return TerminalTaskObservations(
        task_id=task,
        observations=observations,
        source_manifest_digest=digest,
    )
