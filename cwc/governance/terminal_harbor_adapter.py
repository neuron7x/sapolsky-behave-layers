from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Mapping

from cwc.governance.benchmark_runtime import verify_benchmark_runtime
from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.frozen_action_catalog import load_frozen_action_catalog
from cwc.governance.frozen_observation_runtime import invoke_frozen_observation_provider
from cwc.governance.frozen_policy_runtime import invoke_frozen_policy
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.runtime_cost_contract import (
    RuntimeCostContractError,
    parse_runtime_cost_contract,
    runtime_physical_cost_evidence,
)
from cwc.governance.sandbox_image_population import SandboxImagePopulationError
from cwc.governance.terminal_sandbox_authority import (
    TerminalSandboxAuthorityError,
    verify_terminal_sandbox_environment,
)
from cwc.governance.terminal_bench_admission import admit_terminal_bench_trial
from cwc.governance.terminal_task_overlay import (
    TerminalTaskOverlayError,
    prepare_terminal_task_overlay,
)

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


def _sandbox_image_binding(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    task_id: str,
):
    environment = _component_json(
        repository_root=repository_root,
        execution_freeze=execution_freeze,
        component="environment",
        schema="DGC_ENVIRONMENT_MANIFEST_V2",
    )
    try:
        population = verify_terminal_sandbox_environment(
            repository_root=repository_root,
            environment=environment,
        )
    except TerminalSandboxAuthorityError as exc:
        raise TerminalHarborAdapterError(
            f"Terminal sandbox environment authority replay failed: {exc}"
        ) from exc
    try:
        binding = population.resolve(task_id)
    except SandboxImagePopulationError as exc:
        raise TerminalHarborAdapterError(
            "sandbox image binding missing for frozen task"
        ) from exc
    return environment, population, binding

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
            "top-level Harbor agent_result required for DGC telemetry"
        )
    metadata = agent.get("metadata")
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise TerminalHarborAdapterError("Harbor agent metadata must be an object")
    return {str(k): v for k, v in metadata.items()}


def _component_sha(
    execution_freeze: Mapping[str, object],
    component: str,
) -> str:
    rows = execution_freeze.get("components")
    if not isinstance(rows, list):
        raise TerminalHarborAdapterError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == component
    ]
    if len(matches) != 1:
        raise TerminalHarborAdapterError(f"exactly one {component} required")
    return _sha(f"{component} sha256", matches[0].get("sha256"))


def _frozen_rate_card(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    provider: str,
    model_id: str,
    model_version: str,
) -> ProviderRateCard:
    pricing = _component_json(
        repository_root=repository_root,
        execution_freeze=execution_freeze,
        component="pricing_snapshot",
        schema="DGC_PRICING_SNAPSHOT_V1",
    )
    captured_at = str(pricing.get("captured_at", "")).strip()
    rows = pricing.get("entries")
    if not captured_at or not isinstance(rows, list):
        raise TerminalHarborAdapterError("frozen pricing snapshot incomplete")
    matches = [
        row for row in rows
        if isinstance(row, Mapping)
        and (
            str(row.get("provider", "")).strip(),
            str(row.get("model_id", "")).strip(),
            str(row.get("model_version", "")).strip(),
        ) == (provider, model_id, model_version)
    ]
    if len(matches) != 1:
        raise TerminalHarborAdapterError(
            "selected action lacks exactly one frozen pricing identity"
        )
    row = matches[0]
    if str(row.get("currency", "")) != "USD":
        raise TerminalHarborAdapterError("frozen model pricing must be USD")
    try:
        return ProviderRateCard(
            provider=provider,
            model=model_id,
            input_usd_per_million=float(row["input_per_million"]),
            cached_input_usd_per_million=float(row["cached_input_per_million"]),
            cache_write_usd_per_million=float(row["cache_write_per_million"]),
            long_cache_write_usd_per_million=float(
                row["long_cache_write_per_million"]
            ),
            output_usd_per_million=float(row["output_per_million"]),
            source_uri=str(row["source_uri"]),
            retrieved_at=captured_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TerminalHarborAdapterError("invalid frozen selected-action pricing") from exc


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise TerminalHarborAdapterError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TerminalHarborAdapterError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise TerminalHarborAdapterError(f"{name} must be >= 0")
    return parsed


def _native_runtime_trace(
    *,
    trial_dir: Path,
    admitted,
    action,
    policy_id: str,
    task_id: str,
    replicate: int,
    rate_card: ProviderRateCard,
) -> dict[str, object]:
    trajectory_path = trial_dir / "agent" / "trajectory.json"
    if trajectory_path.is_symlink() or not trajectory_path.is_file():
        raise TerminalHarborAdapterError("native Harbor ATIF trajectory missing")
    if sha256_file(trajectory_path) != admitted.trajectory_sha256:
        raise TerminalHarborAdapterError("native Harbor trajectory digest drift")
    try:
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalHarborAdapterError("invalid native Harbor ATIF trajectory") from exc
    if not isinstance(trajectory, Mapping) or trajectory.get("schema_version") != "ATIF-v1.7":
        raise TerminalHarborAdapterError(
            "native runtime telemetry requires Harbor Codex ATIF-v1.7"
        )
    session_id = str(trajectory.get("session_id", "")).strip()
    if not session_id:
        raise TerminalHarborAdapterError("native ATIF session_id required")
    agent = trajectory.get("agent")
    if not isinstance(agent, Mapping):
        raise TerminalHarborAdapterError("native ATIF agent identity missing")
    if str(agent.get("name", "")).strip() != action.harbor_agent:
        raise TerminalHarborAdapterError("native ATIF agent differs from frozen action")
    if str(agent.get("version", "")).strip() != action.agent_version:
        raise TerminalHarborAdapterError(
            "native ATIF agent version differs from frozen action"
        )
    if str(agent.get("model_name", "")).strip() != action.model_id:
        raise TerminalHarborAdapterError("native ATIF model differs from frozen action")
    metrics = trajectory.get("final_metrics")
    if not isinstance(metrics, Mapping):
        raise TerminalHarborAdapterError("native ATIF final_metrics required")
    input_tokens = _nonnegative_int(
        "ATIF total_prompt_tokens", metrics.get("total_prompt_tokens")
    )
    cached_tokens = _nonnegative_int(
        "ATIF total_cached_tokens", metrics.get("total_cached_tokens", 0)
    )
    output_tokens = _nonnegative_int(
        "ATIF total_completion_tokens", metrics.get("total_completion_tokens")
    )
    if (
        input_tokens != admitted.n_input_tokens
        or cached_tokens != admitted.n_cache_tokens
        or output_tokens != admitted.n_output_tokens
    ):
        raise TerminalHarborAdapterError(
            "ATIF token totals differ from Harbor result AgentContext"
        )
    extra = metrics.get("extra")
    if extra is None:
        extra = {}
    if not isinstance(extra, Mapping):
        raise TerminalHarborAdapterError("native ATIF final_metrics.extra malformed")
    cache_write_tokens = _nonnegative_int(
        "ATIF total_cache_write_input_tokens",
        extra.get("total_cache_write_input_tokens", 0),
    )
    if cached_tokens + cache_write_tokens > input_tokens:
        raise TerminalHarborAdapterError(
            "ATIF cached/cache-write subsets exceed total prompt tokens"
        )
    decision_id = f"{task_id}::{policy_id}::{replicate}"
    source_digest = admitted.trajectory_sha256
    runtime_call_id = f"harbor-atif:{session_id}:aggregate"
    trace_id = sha256_bytes(
        canonical_json_bytes({
            "authority": "RUNTIME_LIVE",
            "decision_id": decision_id,
            "runtime_call_id": runtime_call_id,
            "source_artifact_digest": source_digest,
            "model": action.model_id,
            "model_version": action.model_version,
        })
    )
    return {
        "trace_id": trace_id,
        "decision_id": decision_id,
        "policy_id": policy_id,
        "authority": "RUNTIME_LIVE",
        "provider": action.provider,
        "model": action.model_id,
        "model_version": action.model_version,
        "rate_card_digest": rate_card.digest,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "long_cache_write_tokens": 0,
        "output_tokens": output_tokens,
        "provider_request_id": None,
        "runtime_call_id": runtime_call_id,
        "source_artifact_digest": source_digest,
    }


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
    adapter_started_ns = time.monotonic_ns()

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

    environment, sandbox_population, sandbox_binding = _sandbox_image_binding(
        repository_root=root,
        execution_freeze=execution,
        task_id=task_id,
    )
    overlay_parent = unit_root / "task-overlay"
    try:
        overlay = prepare_terminal_task_overlay(
            task_id=task_id,
            task_root=task_root,
            destination_root=overlay_parent,
            binding=sandbox_binding,
        )
    except TerminalTaskOverlayError as exc:
        raise TerminalHarborAdapterError("immutable OCI task overlay rejected") from exc
    execution_task_root = overlay_parent / task_id

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
        "--path", str(execution_task_root),
        "--env", "docker",
        "--no-force-build",
        "--delete",
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
    runtime_cost_measurement: dict[str, object] | None = None
    native_actual_cost: float | None = None
    if "dgc_provider_usage_traces" in metadata:
        traces = _provider_traces(
            metadata,
            policy_id=policy_id,
            action_provider=action.provider,
            action_model=action.model_id,
            action_model_version=action.model_version,
        )
        physical = metadata.get("dgc_physical_cost_evidence")
        if not isinstance(physical, Mapping):
            raise TerminalHarborAdapterError(
                "complete dgc_physical_cost_evidence required with custom provider telemetry"
            )
        physical_doc = {str(k): v for k, v in physical.items()}
        telemetry_authority = "PROVIDER_LIVE"
    else:
        rate_card = _frozen_rate_card(
            repository_root=root,
            execution_freeze=execution,
            provider=action.provider,
            model_id=action.model_id,
            model_version=action.model_version,
        )
        runtime_trace = _native_runtime_trace(
            trial_dir=trial_dir,
            admitted=admitted,
            action=action,
            policy_id=policy_id,
            task_id=task_id,
            replicate=replicate,
            rate_card=rate_card,
        )
        traces = [runtime_trace]
        elapsed_ns = time.monotonic_ns() - adapter_started_ns
        try:
            cost_contract = parse_runtime_cost_contract(
                budget.get("runtime_cost_contract")
            )
            physical_doc, runtime_cost_measurement, infra_usd = (
                runtime_physical_cost_evidence(
                    contract=cost_contract,
                    budget_manifest_sha256=_component_sha(execution, "budget"),
                    elapsed_ns=elapsed_ns,
                )
            )
        except RuntimeCostContractError as exc:
            raise TerminalHarborAdapterError(
                "frozen runtime cost contract rejected"
            ) from exc
        model_usd = rate_card.token_cost_usd(
            input_tokens=int(runtime_trace["input_tokens"]),
            cached_input_tokens=int(runtime_trace["cached_input_tokens"]),
            cache_write_tokens=int(runtime_trace["cache_write_tokens"]),
            long_cache_write_tokens=int(runtime_trace["long_cache_write_tokens"]),
            output_tokens=int(runtime_trace["output_tokens"]),
        )
        native_actual_cost = model_usd + infra_usd
        telemetry_authority = "RUNTIME_LIVE"

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
            "sandbox_image": {
                "runtime": sandbox_population.runtime,
                "population_digest": sandbox_population.population_digest,
                "task_id": sandbox_binding.task_id,
                "task_source_sha256": sandbox_binding.task_source_sha256,
                "build_context_sha256": sandbox_binding.build_context_sha256,
                "image_reference": sandbox_binding.image_reference,
                "container_image_digest": sandbox_binding.container_image_digest,
                "build_receipt_path": sandbox_binding.build_receipt_path,
                "build_receipt_sha256": sandbox_binding.build_receipt_sha256,
                "build_receipt_digest": sandbox_binding.build_receipt_digest,
                "verified_receipt_digest": sandbox_binding.build_receipt_digest,
                "environment_manifest_runtime": environment.get("runtime"),
            },
            "task_overlay": overlay.document,
            "telemetry_authority": telemetry_authority,
            "runtime_cost_measurement": runtime_cost_measurement,
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
    if native_actual_cost is not None:
        response["actual_cost_usd"] = native_actual_cost
    elif "dgc_actual_cost_usd" in metadata:
        try:
            declared = float(metadata["dgc_actual_cost_usd"])
        except (TypeError, ValueError) as exc:
            raise TerminalHarborAdapterError("dgc_actual_cost_usd must be numeric") from exc
        if not math.isfinite(declared) or declared < 0:
            raise TerminalHarborAdapterError("dgc_actual_cost_usd must be finite and >=0")
        response["actual_cost_usd"] = declared
    return response
