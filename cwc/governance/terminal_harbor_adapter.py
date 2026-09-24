from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Mapping

from cwc.governance.benchmark_runtime import verify_benchmark_runtime
from cwc.governance.frozen_action_catalog import load_frozen_action_catalog
from cwc.governance.frozen_observation_runtime import invoke_frozen_observation_provider
from cwc.governance.frozen_policy_runtime import invoke_frozen_policy
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file
from cwc.governance.terminal_bench_admission import admit_terminal_bench_trial

FAMILY = "TERMINAL_BENCH_2_1"
REQUEST_SCHEMA = "DGC_UNIT_EXECUTION_REQUEST_V1"
RESPONSE_SCHEMA = "DGC_UNIT_EXECUTION_RESPONSE_V1"


class TerminalHarborAdapterError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise TerminalHarborAdapterError(f"{name} must be lowercase SHA-256")
    return text


def _safe_repo_file(root: Path, value: object) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise TerminalHarborAdapterError("manifest path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise TerminalHarborAdapterError(f"manifest symlink rejected: {rel.as_posix()}")
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise TerminalHarborAdapterError("manifest path escapes repository root") from exc
    if not path.is_file():
        raise TerminalHarborAdapterError(f"manifest file missing: {rel.as_posix()}")
    return path


def _component_json(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    component: str,
    schema: str,
) -> dict[str, object]:
    rows = execution_freeze.get("components")
    if not isinstance(rows, list):
        raise TerminalHarborAdapterError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == component
    ]
    if len(matches) != 1:
        raise TerminalHarborAdapterError(f"exactly one {component} required")
    row = matches[0]
    path = _safe_repo_file(repository_root, row.get("path"))
    if sha256_file(path) != _sha(f"{component} sha256", row.get("sha256")):
        raise TerminalHarborAdapterError(f"{component} bytes differ from execution freeze")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalHarborAdapterError(f"invalid {component} JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise TerminalHarborAdapterError(f"{component} schema mismatch")
    return doc


def _finite_positive(name: str, value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TerminalHarborAdapterError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise TerminalHarborAdapterError(f"{name} must be finite and > 0")
    return parsed


def _unit(request: Mapping[str, object]) -> dict[str, object]:
    raw = request.get("unit")
    if not isinstance(raw, Mapping):
        raise TerminalHarborAdapterError("unit missing")
    unit = {str(k): v for k, v in raw.items()}
    required = {"task_id", "policy_id", "replicate"}
    if not required.issubset(unit):
        raise TerminalHarborAdapterError("unit identity incomplete")
    if not str(unit["task_id"]).strip() or not str(unit["policy_id"]).strip():
        raise TerminalHarborAdapterError("unit task/policy identity empty")
    return unit


def _trial_dir(job_dir: Path) -> Path:
    if not job_dir.is_dir():
        raise TerminalHarborAdapterError("Harbor job directory missing")
    trials = [
        child for child in sorted(job_dir.iterdir(), key=lambda p: p.name)
        if child.is_dir() and not child.is_symlink() and (child / "result.json").is_file()
    ]
    if len(trials) != 1:
        raise TerminalHarborAdapterError(
            f"Harbor single-task job must produce exactly one trial; observed={len(trials)}"
        )
    return trials[0]


def _raw_trial_result(trial_dir: Path) -> dict[str, object]:
    path = trial_dir / "result.json"
    if path.is_symlink() or not path.is_file():
        raise TerminalHarborAdapterError("Harbor trial result must be a regular file")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalHarborAdapterError("invalid Harbor trial result JSON") from exc
    if not isinstance(doc, dict):
        raise TerminalHarborAdapterError("Harbor trial result must be an object")
    return doc


def _dgc_agent_metadata(trial: Mapping[str, object]) -> dict[str, object]:
    agent = trial.get("agent_result")
    if not isinstance(agent, Mapping):
        raise TerminalHarborAdapterError(
            "top-level Harbor agent_result required for DGC confirmatory telemetry"
        )
    metadata = agent.get("metadata")
    if not isinstance(metadata, Mapping):
        raise TerminalHarborAdapterError("Harbor agent metadata missing DGC evidence envelope")
    return {str(k): v for k, v in metadata.items()}


def _provider_traces(
    metadata: Mapping[str, object],
    *,
    policy_id: str,
    action_provider: str,
    action_model: str,
    action_model_version: str,
) -> list[dict[str, object]]:
    raw = metadata.get("dgc_provider_usage_traces")
    if not isinstance(raw, list) or not raw or not all(isinstance(row, Mapping) for row in raw):
        raise TerminalHarborAdapterError("real dgc_provider_usage_traces required")
    rows = [{str(k): v for k, v in row.items()} for row in raw]
    request_ids: set[str] = set()
    selected_action_seen = False
    for row in rows:
        if str(row.get("policy_id", "")).strip() != policy_id:
            raise TerminalHarborAdapterError("provider trace policy identity mismatch")
        request_id = str(row.get("provider_request_id", "")).strip()
        if not request_id:
            raise TerminalHarborAdapterError("provider trace requires real provider_request_id")
        if request_id in request_ids:
            raise TerminalHarborAdapterError("duplicate provider_request_id in Harbor telemetry")
        request_ids.add(request_id)
        identity = (
            str(row.get("provider", "")).strip(),
            str(row.get("model", "")).strip(),
            str(row.get("model_version", "")).strip(),
        )
        if identity == (action_provider, action_model, action_model_version):
            selected_action_seen = True
    if not selected_action_seen:
        raise TerminalHarborAdapterError(
            "Harbor provider telemetry does not contain the frozen selected action model identity"
        )
    return rows


def execute_terminal_harbor_unit(
    *,
    request: Mapping[str, object],
    repository_root: Path,
    materialization_root: Path,
    runtime_root: Path,
    unit_runtime_root: Path,
) -> dict[str, object]:
    if request.get("schema") != REQUEST_SCHEMA:
        raise TerminalHarborAdapterError("unexpected unit request schema")
    if request.get("family_id") != FAMILY:
        raise TerminalHarborAdapterError("Terminal adapter family mismatch")
    root = Path(repository_root).resolve()
    materialization = Path(materialization_root).resolve()
    unit_root = Path(unit_runtime_root).resolve()
    if not root.is_dir() or not materialization.is_dir() or not unit_root.is_dir():
        raise TerminalHarborAdapterError("required execution root missing")

    unit = _unit(request)
    task_id = str(unit["task_id"]).strip()
    policy_id = str(unit["policy_id"]).strip()
    try:
        replicate = int(unit["replicate"])
        attempt = int(request.get("attempt"))
    except (TypeError, ValueError) as exc:
        raise TerminalHarborAdapterError("replicate/attempt identity malformed") from exc
    if replicate < 0 or attempt <= 0:
        raise TerminalHarborAdapterError("replicate must be >=0 and attempt must be >0")

    components = request.get("frozen_components")
    if not isinstance(components, list):
        raise TerminalHarborAdapterError("frozen component population missing")
    execution = {"components": components}

    budget = _component_json(
        repository_root=root,
        execution_freeze=execution,
        component="budget",
        schema="DGC_BUDGET_MANIFEST_V1",
    )
    max_cost = _finite_positive("max_cost_usd", budget.get("max_cost_usd"))
    max_wall = _finite_positive("max_wall_time_s", budget.get("max_wall_time_s"))

    runtime = verify_benchmark_runtime(
        repository_root=root,
        execution_freeze=execution,
        runtime_root=runtime_root,
        family_id=FAMILY,
    )
    if runtime.runtime_name != "harbor":
        raise TerminalHarborAdapterError("Terminal adapter requires frozen Harbor runtime")

    observations = invoke_frozen_observation_provider(
        repository_root=root,
        execution_freeze=execution,
        materialization_root=materialization,
        family_id=FAMILY,
        task_id=task_id,
        budget_remaining=max_cost,
        step_index=0,
    )

    frozen_policy = request.get("governance_policy")
    if not isinstance(frozen_policy, Mapping) or str(frozen_policy.get("policy_id", "")) != policy_id:
        raise TerminalHarborAdapterError("frozen governance policy does not match work unit")
    decision = invoke_frozen_policy(
        repository_root=root,
        frozen_policy=frozen_policy,
        task_id=task_id,
        replicate=replicate,
        observations=observations.observations,
        state={},
    )

    catalog = load_frozen_action_catalog(
        repository_root=root,
        execution_freeze=execution,
    )
    action = catalog.resolve(decision.action_id)

    task_root = materialization / FAMILY / "repo" / "tasks" / task_id
    if task_root.is_symlink() or not task_root.is_dir():
        raise TerminalHarborAdapterError("materialized Terminal task root missing or symlinked")

    stable = hashlib.sha256(
        canonical_json_bytes({
            "generation_id": request.get("generation_id"),
            "unit": unit,
            "attempt": attempt,
            "action_id": action.action_id,
        })
    ).hexdigest()
    job_name = f"dgc-{stable[:20]}"
    jobs_dir = unit_root / "harbor-jobs"
    if jobs_dir.exists():
        raise TerminalHarborAdapterError("Harbor jobs directory must not pre-exist")

    command = [
        *runtime.invocation,
        "run",
        "--path", str(task_root),
        "--agent", action.harbor_agent_argument,
        "--model", action.harbor_model_argument,
        "--job-name", job_name,
        "--jobs-dir", str(jobs_dir),
        "--n-attempts", "1",
        "--n-concurrent", "1",
        "--max-retries", "0",
        "--yes",
        "--quiet",
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=Path(runtime.runtime_root),
            env=dict(os.environ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max_wall,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TerminalHarborAdapterError("Harbor unit exceeded frozen wall-time budget") from exc
    except OSError as exc:
        raise TerminalHarborAdapterError("frozen Harbor runtime could not start") from exc
    harbor_stdout = bytes(proc.stdout or b"")
    harbor_stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise TerminalHarborAdapterError(f"Harbor unit exited nonzero: {proc.returncode}")

    job_dir = jobs_dir / job_name
    trial_dir = _trial_dir(job_dir)
    admitted = admit_terminal_bench_trial(
        trial_root=trial_dir,
        expected_task_id=task_id,
    )
    raw_trial = _raw_trial_result(trial_dir)

    agent_info = raw_trial.get("agent_info")
    if not isinstance(agent_info, Mapping):
        raise TerminalHarborAdapterError("Harbor agent_info missing")
    if str(agent_info.get("name", "")).strip() != action.harbor_agent:
        raise TerminalHarborAdapterError("Harbor executed agent identity differs from frozen action")
    if str(agent_info.get("version", "")).strip() != action.agent_version:
        raise TerminalHarborAdapterError("Harbor executed agent version differs from frozen action")
    model_info = agent_info.get("model_info")
    if not isinstance(model_info, Mapping):
        raise TerminalHarborAdapterError("Harbor model_info missing")
    if str(model_info.get("provider", "")).strip() != action.provider:
        raise TerminalHarborAdapterError("Harbor provider differs from frozen action")
    if str(model_info.get("name", "")).strip() != action.model_id:
        raise TerminalHarborAdapterError("Harbor model differs from frozen action")

    metadata = _dgc_agent_metadata(raw_trial)
    traces = _provider_traces(
        metadata,
        policy_id=policy_id,
        action_provider=action.provider,
        action_model=action.model_id,
        action_model_version=action.model_version,
    )
    physical = metadata.get("dgc_physical_cost_evidence")
    if not isinstance(physical, Mapping):
        raise TerminalHarborAdapterError("complete dgc_physical_cost_evidence required")
    physical_doc = {str(k): v for k, v in physical.items()}

    response: dict[str, object] = {
        "schema": RESPONSE_SCHEMA,
        "unit": unit,
        "attempt": attempt,
        "quality": admitted.quality,
        "provider_usage_traces": traces,
        "physical_cost_evidence": physical_doc,
        "trace": {
            "family_id": FAMILY,
            "benchmark_runtime": runtime.document,
            "observation": observations.document,
            "policy_decision": decision.document,
            "action": {
                "action_id": action.action_id,
                "harbor_agent": action.harbor_agent,
                "harbor_agent_argument": action.harbor_agent_argument,
                "harbor_model_argument": action.harbor_model_argument,
                "agent_version": action.agent_version,
                "provider": action.provider,
                "model_id": action.model_id,
                "model_version": action.model_version,
            },
            "harbor_command_digest": hashlib.sha256(
                canonical_json_bytes(command)
            ).hexdigest(),
            "harbor_stdout_sha256": hashlib.sha256(harbor_stdout).hexdigest(),
            "harbor_stderr_sha256": hashlib.sha256(harbor_stderr).hexdigest(),
            "trial_result_sha256": admitted.result_sha256,
            "trajectory_sha256": admitted.trajectory_sha256,
            "admission_evidence_digest": admitted.evidence_digest,
            "job_name": job_name,
            "trial_name": admitted.trial_name,
        },
    }
    if "dgc_actual_cost_usd" in metadata:
        try:
            declared = float(metadata["dgc_actual_cost_usd"])
        except (TypeError, ValueError) as exc:
            raise TerminalHarborAdapterError("dgc_actual_cost_usd must be numeric") from exc
        if not math.isfinite(declared) or declared < 0:
            raise TerminalHarborAdapterError("dgc_actual_cost_usd must be finite and >=0")
        response["actual_cost_usd"] = declared
    return response
