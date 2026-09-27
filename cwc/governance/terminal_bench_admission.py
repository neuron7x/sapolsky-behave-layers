from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SCHEMA = "DGC_TERMINAL_BENCH_ADMISSION_V1"


class TerminalBenchAdmissionError(RuntimeError):
    pass


def _regular_file(root: Path, relative: str) -> Path:
    rel = Path(str(relative))
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise TerminalBenchAdmissionError("evidence path must be relative and non-traversing")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise TerminalBenchAdmissionError(f"symlink evidence path rejected: {relative}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise TerminalBenchAdmissionError("evidence path escapes trial root") from exc
    if not resolved.is_file():
        raise TerminalBenchAdmissionError(f"missing evidence file: {relative}")
    return resolved


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise TerminalBenchAdmissionError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TerminalBenchAdmissionError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise TerminalBenchAdmissionError(f"{name} must be >= 0")
    return parsed


def _finite_nonnegative(name: str, value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TerminalBenchAdmissionError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0.0:
        raise TerminalBenchAdmissionError(f"{name} must be finite and >= 0")
    return parsed


def _quality_from_rewards(verifier_result: Mapping[str, object]) -> float:
    rewards = verifier_result.get("rewards")
    if not isinstance(rewards, Mapping) or not rewards:
        raise TerminalBenchAdmissionError("Harbor verifier_result.rewards missing")
    if "reward" in rewards:
        raw = rewards["reward"]
    elif len(rewards) == 1:
        raw = next(iter(rewards.values()))
    else:
        raise TerminalBenchAdmissionError(
            "multiple Harbor rewards require an explicit upstream primary reward"
        )
    try:
        quality = float(raw)
    except (TypeError, ValueError) as exc:
        raise TerminalBenchAdmissionError("Harbor primary reward must be numeric") from exc
    if not math.isfinite(quality) or not 0.0 <= quality <= 1.0:
        raise TerminalBenchAdmissionError("Harbor primary reward must be finite in [0,1]")
    return quality


@dataclass(frozen=True, slots=True)
class TerminalBenchAdmission:
    task_id: str
    trial_name: str
    quality: float
    agent_metered_cost_usd: float
    n_input_tokens: int
    n_cache_tokens: int
    n_output_tokens: int
    provider: str
    model: str
    result_sha256: str
    trajectory_sha256: str
    evidence_digest: str
    physical_cost_authority: bool = False
    provider_live_authority: bool = False
    product_promotion_authorized: bool = False
    schema: str = SCHEMA

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "trial_name": self.trial_name,
            "quality": self.quality,
            "agent_metered_cost_usd": self.agent_metered_cost_usd,
            "n_input_tokens": self.n_input_tokens,
            "n_cache_tokens": self.n_cache_tokens,
            "n_output_tokens": self.n_output_tokens,
            "provider": self.provider,
            "model": self.model,
            "result_sha256": self.result_sha256,
            "trajectory_sha256": self.trajectory_sha256,
            "evidence_digest": self.evidence_digest,
            "physical_cost_authority": False,
            "provider_live_authority": False,
            "product_promotion_authorized": False,
        }


def admit_terminal_bench_trial(
    *,
    trial_root: Path,
    expected_task_id: str,
    result_relative_path: str = "result.json",
    trajectory_relative_path: str = "agent/trajectory.json",
) -> TerminalBenchAdmission:
    root = Path(trial_root).resolve()
    if not root.is_dir():
        raise TerminalBenchAdmissionError("trial root missing")
    task_id = str(expected_task_id).strip()
    if not task_id:
        raise TerminalBenchAdmissionError("expected_task_id required")

    result_path = _regular_file(root, result_relative_path)
    trajectory_path = _regular_file(root, trajectory_relative_path)
    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalBenchAdmissionError("invalid Harbor trial result JSON") from exc
    if not isinstance(raw, Mapping):
        raise TerminalBenchAdmissionError("Harbor trial result must be a JSON object")

    observed_task = str(raw.get("task_name", "")).strip()
    if observed_task != task_id:
        raise TerminalBenchAdmissionError("Harbor task identity differs from frozen work unit")
    trial_name = str(raw.get("trial_name", "")).strip()
    if not trial_name:
        raise TerminalBenchAdmissionError("Harbor trial_name missing")

    verifier = raw.get("verifier_result")
    if not isinstance(verifier, Mapping):
        raise TerminalBenchAdmissionError("Harbor verifier_result missing")
    quality = _quality_from_rewards(verifier)

    agent = raw.get("agent_result")
    if not isinstance(agent, Mapping):
        raise TerminalBenchAdmissionError("Harbor agent_result missing")
    n_input = _nonnegative_int("n_input_tokens", agent.get("n_input_tokens"))
    n_cache = _nonnegative_int("n_cache_tokens", agent.get("n_cache_tokens"))
    n_output = _nonnegative_int("n_output_tokens", agent.get("n_output_tokens"))
    if n_cache > n_input:
        raise TerminalBenchAdmissionError("n_cache_tokens cannot exceed n_input_tokens")
    agent_cost = _finite_nonnegative("agent_result.cost_usd", agent.get("cost_usd"))

    agent_info = raw.get("agent_info")
    if not isinstance(agent_info, Mapping):
        raise TerminalBenchAdmissionError("Harbor agent_info missing")
    model_info = agent_info.get("model_info")
    if not isinstance(model_info, Mapping):
        raise TerminalBenchAdmissionError("Harbor model_info missing")
    provider = str(model_info.get("provider", "")).strip()
    model = str(model_info.get("name", "")).strip()
    if not provider or not model:
        raise TerminalBenchAdmissionError("Harbor provider/model identity missing")

    result_sha = _sha256(result_path)
    trajectory_sha = _sha256(trajectory_path)
    evidence_digest = hashlib.sha256(
        json.dumps(
            {
                "task_id": task_id,
                "trial_name": trial_name,
                "quality": quality,
                "agent_metered_cost_usd": agent_cost,
                "n_input_tokens": n_input,
                "n_cache_tokens": n_cache,
                "n_output_tokens": n_output,
                "provider": provider,
                "model": model,
                "result_sha256": result_sha,
                "trajectory_sha256": trajectory_sha,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return TerminalBenchAdmission(
        task_id=task_id,
        trial_name=trial_name,
        quality=quality,
        agent_metered_cost_usd=agent_cost,
        n_input_tokens=n_input,
        n_cache_tokens=n_cache,
        n_output_tokens=n_output,
        provider=provider,
        model=model,
        result_sha256=result_sha,
        trajectory_sha256=trajectory_sha,
        evidence_digest=evidence_digest,
    )
