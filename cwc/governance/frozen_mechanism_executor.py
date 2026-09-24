from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec
from cwc.governance.execution_manifest_freeze import (
    EXECUTOR_REQUEST_SCHEMA,
    verify_execution_manifest_freeze_document,
)
from cwc.governance.external_evidence_reference import verify_materialization_generation
from cwc.governance.frozen_panel_executor import (
    FrozenPanelExecutionError,
    _assert_git_identity,
    _audit_document,
    _executor_manifest,
    _finite_probability,
    _invoke,
    _physical_cost_certificate,
    _pricing_rate_cards,
    _provider_model_meter,
    _policy_subject,
    _runtime_env,
    _write_json,
)
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.mechanism_execution_authority import (
    verify_mechanism_execution_authority_document,
)
from cwc.governance.mechanism_execution_bundle import (
    BUNDLE_SCHEMA,
    EVIDENCE_SCHEMA,
    RESULT_SCHEMA,
    canonical_mechanism_result_digest,
    verify_mechanism_execution_bundle,
)

_FORBIDDEN_RISK_FIELDS = frozenset({
    "catastrophic_regret",
    "risk_endpoint_response",
    "risk_endpoint_response_digest",
    "risk_endpoint_manifest_sha256",
})


class FrozenMechanismExecutionError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenMechanismExecutionError(f"{name} must be lowercase SHA-256")
    return text


def _mechanism_request(
    *,
    repository_root: Path,
    execution: Mapping[str, object],
    authority: Mapping[str, object],
    lease,
) -> dict[str, object]:
    components = execution.get("components")
    if not isinstance(components, list):
        raise FrozenMechanismExecutionError(
            "frozen execution component population missing"
        )
    try:
        policy = _policy_subject(
            root=repository_root,
            execution=execution,
            policy_id=lease.unit.policy_id,
        )
    except FrozenPanelExecutionError as exc:
        raise FrozenMechanismExecutionError(str(exc)) from exc
    return {
        "schema": EXECUTOR_REQUEST_SCHEMA,
        "authority_kind": "MECHANISM_EXECUTION",
        "family_id": authority["family_id"],
        "mechanism_authority_digest": authority["authority_digest"],
        "distributed_spec_digest": authority["distributed_spec_digest"],
        "materialization_reference_digest": execution[
            "materialization_reference_digest"
        ],
        "unit": asdict(lease.unit),
        "attempt": lease.attempt,
        "frozen_components": components,
        "governance_policy": policy,
    }


def execute_frozen_mechanism_panel(
    *,
    repository_root: Path,
    execution_manifest_freeze_path: Path,
    harness_freeze_path: Path,
    mechanism_authority_path: Path,
    materialization_generation_root: Path,
    source_registry_path: Path,
    output_root: Path,
    worker_id: str = "dgc-mechanism-executor",
) -> Path:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise FrozenMechanismExecutionError("repository root missing")

    execution = verify_execution_manifest_freeze_document(
        Path(execution_manifest_freeze_path)
    )
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    authority = verify_mechanism_execution_authority_document(
        Path(mechanism_authority_path)
    )
    execution_digest = _sha("execution freeze digest", execution.get("freeze_digest"))
    harness_digest = _sha("harness freeze digest", harness.get("harness_freeze_digest"))
    if authority.get("execution_manifest_freeze_digest") != execution_digest:
        raise FrozenMechanismExecutionError(
            "mechanism authority execution-freeze lineage mismatch"
        )
    if authority.get("harness_freeze_digest") != harness_digest:
        raise FrozenMechanismExecutionError(
            "mechanism authority harness lineage mismatch"
        )
    if harness.get("execution_manifest_freeze_digest") != execution_digest:
        raise FrozenMechanismExecutionError(
            "harness belongs to different execution freeze"
        )
    family = str(authority.get("family_id", "")).strip()
    if family != str(execution.get("family_id", "")).strip():
        raise FrozenMechanismExecutionError("mechanism family differs from execution freeze")
    if family != str(harness.get("family_id", "")).strip():
        raise FrozenMechanismExecutionError("mechanism family differs from harness")

    try:
        _assert_git_identity(root, execution)
    except FrozenPanelExecutionError as exc:
        raise FrozenMechanismExecutionError(str(exc)) from exc

    reference = verify_materialization_generation(
        Path(materialization_generation_root),
        expected_repository_commit=str(execution["repository_commit"]),
        expected_repository_tree=str(execution["repository_tree"]),
        source_registry_path=Path(source_registry_path),
    )
    if reference.digest != _sha(
        "materialization reference digest",
        execution.get("materialization_reference_digest"),
    ):
        raise FrozenMechanismExecutionError(
            "materialized bytes differ from frozen execution reference"
        )
    if (
        reference.binding(family).materialized_task_manifest_sha256
        != execution.get("task_manifest_digest")
    ):
        raise FrozenMechanismExecutionError(
            "materialized task population differs from execution freeze"
        )

    try:
        executor, argv, timeout = _executor_manifest(root, execution)
        rate_cards, pricing_component_sha = _pricing_rate_cards(root, execution)
    except FrozenPanelExecutionError as exc:
        raise FrozenMechanismExecutionError(str(exc)) from exc

    spec_doc = authority.get("distributed_spec")
    if not isinstance(spec_doc, Mapping):
        raise FrozenMechanismExecutionError("mechanism distributed spec missing")
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise FrozenMechanismExecutionError(
            "mechanism distributed spec cannot be reconstructed"
        ) from exc
    if spec.digest != authority.get("distributed_spec_digest"):
        raise FrozenMechanismExecutionError("mechanism distributed spec digest mismatch")

    coordinator = DistributedEvalCoordinator(spec)
    final = Path(output_root)
    if final.exists():
        raise FileExistsError("mechanism bundle output is immutable")
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{final.name}.staging-", dir=final.parent)
    )
    tick = 0
    result_paths: list[str] = []
    result_index = 0

    try:
        materialization_root = Path(materialization_generation_root).resolve()
        env = _runtime_env(root, materialization_root, executor)
        while True:
            lease = coordinator.claim(worker_id, tick=tick)
            if lease is None:
                snapshot = coordinator.snapshot(tick=tick)
                counts = snapshot["counts"]
                if counts.get("COMMITTED") == len(spec.units()):
                    break
                raise FrozenMechanismExecutionError(
                    f"mechanism executor cannot claim remaining frozen units: {counts}"
                )
            tick += 1
            request = _mechanism_request(
                repository_root=root,
                execution=execution,
                authority=authority,
                lease=lease,
            )
            attempt_id = hashlib.sha256(
                f"{lease.unit.stable_id}::{lease.attempt}".encode("utf-8")
            ).hexdigest()[:24]
            transcript_dir = staging / "transcripts" / attempt_id
            transcript_dir.mkdir(parents=True, exist_ok=True)
            unit_runtime_root = transcript_dir / "runtime"
            unit_runtime_root.mkdir(parents=True, exist_ok=False)
            unit_env = dict(env)
            unit_env["DGC_UNIT_RUNTIME_ROOT"] = str(unit_runtime_root)

            try:
                response, stdout, stderr = _invoke(
                    argv=argv,
                    request=request,
                    root=root,
                    env=unit_env,
                    timeout=timeout,
                )
                if any(field in response for field in _FORBIDDEN_RISK_FIELDS):
                    raise FrozenMechanismExecutionError(
                        "mechanism adapter emitted forbidden product-risk field"
                    )
                quality = _finite_probability("quality", response.get("quality"))
                (
                    model_usd,
                    provider_trace_population_digest,
                    provider_trace_docs,
                    provider_rate_card_docs,
                ) = _provider_model_meter(
                    response=response,
                    unit=lease.unit,
                    rate_cards=rate_cards,
                )
                cost_certificate = _physical_cost_certificate(
                    response=response,
                    trial_id=f"{lease.unit.stable_id}::{lease.attempt}",
                    cap=spec.max_cost_per_unit_usd,
                    model_usd=model_usd,
                    model_source_digest=provider_trace_population_digest,
                )
                cost = cost_certificate.cost.total_operational_usd
            except (FrozenPanelExecutionError, FrozenMechanismExecutionError) as exc:
                (transcript_dir / "failure.txt").write_text(
                    str(exc) + "\n", encoding="utf-8"
                )
                tick = max(tick, lease.expires_tick)
                coordinator.snapshot(tick=tick)
                continue

            stdout_path = transcript_dir / "stdout.bin"
            stderr_path = transcript_dir / "stderr.bin"
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)
            response_digest = sha256_bytes(canonical_json_bytes(response))
            trace_digest = sha256_bytes(canonical_json_bytes(response["trace"]))

            evidence_rel = f"evidence/{result_index:08d}.json"
            evidence_path = staging / evidence_rel
            evidence_doc = {
                "schema": EVIDENCE_SCHEMA,
                "request": request,
                "response": response,
                "executor_manifest_sha256": next(
                    row["sha256"]
                    for row in execution["components"]
                    if isinstance(row, Mapping)
                    and row.get("component") == "executor_manifest"
                ),
                "executor_entrypoint_sha256": executor["entrypoint_sha256"],
                "argv": list(argv),
                "unit_runtime_root": unit_runtime_root.relative_to(staging).as_posix(),
                "stdout_path": stdout_path.relative_to(staging).as_posix(),
                "stdout_sha256": sha256_file(stdout_path),
                "stderr_path": stderr_path.relative_to(staging).as_posix(),
                "stderr_sha256": sha256_file(stderr_path),
                "adapter_response_digest": response_digest,
                "trace_digest": trace_digest,
                "pricing_snapshot_manifest_sha256": pricing_component_sha,
                "provider_rate_cards": list(provider_rate_card_docs),
                "provider_usage_traces": list(provider_trace_docs),
                "provider_trace_population_digest": provider_trace_population_digest,
                "physical_cost_certificate": {
                    "trial_id": cost_certificate.trial_id,
                    "digest": cost_certificate.digest,
                    "components": [
                        {
                            "component": item.component,
                            "value_usd": item.value_usd,
                            "authority": item.authority.value,
                            "source_digest": item.source_digest,
                        }
                        for item in cost_certificate.component_evidence
                    ],
                    "total_operational_usd": cost_certificate.cost.total_operational_usd,
                },
            }
            _write_json(evidence_path, evidence_doc)
            evidence_digest = sha256_file(evidence_path)
            result_payload = {
                "quality": quality,
                "adapter_response_digest": response_digest,
                "trace_digest": trace_digest,
                "physical_cost_certificate_digest": cost_certificate.digest,
                "provider_trace_population_digest": provider_trace_population_digest,
                "pricing_snapshot_manifest_sha256": pricing_component_sha,
            }
            try:
                record = coordinator.commit(
                    lease,
                    tick=tick,
                    result_payload=result_payload,
                    evidence_digest=evidence_digest,
                    actual_cost_usd=cost,
                )
            except ValueError as exc:
                raise FrozenMechanismExecutionError(
                    "coordinator rejected mechanism result"
                ) from exc

            record_payload = {
                "authority_digest": authority["authority_digest"],
                "distributed_spec_digest": spec.digest,
                "unit": asdict(record.unit),
                "attempt": record.attempt,
                "worker_id": record.worker_id,
                "committed_tick": record.committed_tick,
                "result_payload": result_payload,
                "result_digest": canonical_mechanism_result_digest(result_payload),
                "actual_cost_usd": record.actual_cost_usd,
                "evidence_path": evidence_rel,
                "evidence_sha256": evidence_digest,
            }
            result_doc = {
                "schema": RESULT_SCHEMA,
                **record_payload,
                "record_digest": sha256_bytes(canonical_json_bytes(record_payload)),
            }
            result_rel = f"records/{result_index:08d}.json"
            _write_json(staging / result_rel, result_doc)
            result_paths.append(result_rel)
            result_index += 1
            tick += 1

        completion = coordinator.completion_certificate(tick=tick)
        if not coordinator.verify_audit_chain():
            raise FrozenMechanismExecutionError(
                "mechanism coordinator audit chain failed self-verification"
            )
        _write_json(staging / "AUDIT_LOG.json", _audit_document(coordinator, spec))
        rows = file_manifest(
            staging,
            excluded_names=frozenset({"MECHANISM_EXECUTION_BUNDLE.json"}),
        )
        payload_manifest = sha256_bytes(canonical_json_bytes(rows))
        manifest_payload = {
            "family_id": family,
            "authority_digest": authority["authority_digest"],
            "distributed_spec_digest": spec.digest,
            "payload_manifest_sha256": payload_manifest,
            "audit_log_path": "AUDIT_LOG.json",
            "result_paths": result_paths,
            "expected_units": completion.expected_units,
            "committed_units": completion.committed_units,
            "audit_root_digest": completion.audit_root_digest,
            "result_population_digest": completion.result_population_digest,
            "total_cost_usd": completion.total_cost_usd,
            "risk_qualification_authorized": False,
            "product_promotion_authorized": False,
            "commercial_claim_authorized": False,
        }
        _write_json(
            staging / "MECHANISM_EXECUTION_BUNDLE.json",
            {
                "schema": BUNDLE_SCHEMA,
                **manifest_payload,
                "bundle_digest": sha256_bytes(canonical_json_bytes(manifest_payload)),
            },
        )
        verify_mechanism_execution_bundle(
            staging,
            mechanism_authority_path=Path(mechanism_authority_path),
            execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
            repository_root=root,
        )
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
