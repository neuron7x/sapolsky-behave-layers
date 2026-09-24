from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.distributed_eval_control import (
    DistributedEvalCoordinator,
    DistributedEvalSpec,
    Lease,
    WorkUnitId,
)
from cwc.governance.execution_evidence_bundle import (
    AUDIT_SCHEMA,
    BUNDLE_SCHEMA,
    RESULT_SCHEMA,
    canonical_result_payload_digest,
    verify_execution_bundle,
)
from cwc.governance.execution_manifest_freeze import (
    EXECUTOR_PROTOCOL,
    EXECUTOR_REQUEST_SCHEMA,
    EXECUTOR_RESPONSE_SCHEMA,
    RISK_ENDPOINT_PROTOCOL,
    RISK_ENDPOINT_REQUEST_SCHEMA,
    RISK_ENDPOINT_RESPONSE_SCHEMA,
    verify_execution_manifest_freeze_document,
)
from cwc.governance.external_evidence_reference import verify_materialization_generation
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.physical_cost_evidence import (
    PRODUCT_COST_COMPONENTS,
    CostAuthority,
    CostComponentEvidence,
    PhysicalCostCertificate,
    certify_physical_trial_cost,
)
from cwc.governance.provider_trace import ProviderUsageTrace, TraceAuthority

EVIDENCE_SCHEMA = "DGC_UNIT_EXECUTION_EVIDENCE_V1"


class FrozenPanelExecutionError(RuntimeError):
    pass


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FrozenPanelExecutionError(f"missing regular JSON subject: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenPanelExecutionError(f"invalid JSON subject: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise FrozenPanelExecutionError(f"unexpected schema for {candidate}")
    return doc


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenPanelExecutionError(f"{name} must be lowercase SHA-256")
    return text


def _safe_repo_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FrozenPanelExecutionError("executor subject path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise FrozenPanelExecutionError(f"executor subject symlink rejected: {rel.as_posix()}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FrozenPanelExecutionError("executor subject escapes repository root") from exc
    if not resolved.is_file():
        raise FrozenPanelExecutionError(f"executor subject missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _capture_git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FrozenPanelExecutionError("repository Git identity cannot be verified") from exc
    return proc.stdout.strip()


def _assert_git_identity(root: Path, execution: Mapping[str, object]) -> None:
    if _capture_git(root, "rev-parse", "HEAD") != str(execution.get("repository_commit", "")):
        raise FrozenPanelExecutionError("repository HEAD differs from frozen execution revision")
    if _capture_git(root, "rev-parse", "HEAD^{tree}") != str(execution.get("repository_tree", "")):
        raise FrozenPanelExecutionError("repository tree differs from frozen execution revision")
    if _capture_git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise FrozenPanelExecutionError("repository must be clean before outcome-bearing execution")


def _executor_manifest(root: Path, execution: Mapping[str, object]) -> tuple[dict[str, object], tuple[str, ...], float]:
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise FrozenPanelExecutionError("execution component population missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("component") == "executor_manifest"]
    if len(matches) != 1:
        raise FrozenPanelExecutionError("exactly one frozen executor manifest is required")
    row = matches[0]
    manifest_path, _ = _safe_repo_file(root, row.get("path"))
    if sha256_file(manifest_path) != _sha("executor component sha256", row.get("sha256")):
        raise FrozenPanelExecutionError("executor manifest bytes differ from execution freeze")
    doc = _json(manifest_path, schema="DGC_EXECUTOR_MANIFEST_V1")
    if doc.get("protocol") != EXECUTOR_PROTOCOL:
        raise FrozenPanelExecutionError("executor protocol identity mismatch")
    if doc.get("request_schema") != EXECUTOR_REQUEST_SCHEMA or doc.get("response_schema") != EXECUTOR_RESPONSE_SCHEMA:
        raise FrozenPanelExecutionError("executor request/response schema identity mismatch")
    entrypoint, entrypoint_rel = _safe_repo_file(root, doc.get("entrypoint_path"))
    if sha256_file(entrypoint) != _sha("executor entrypoint sha256", doc.get("entrypoint_sha256")):
        raise FrozenPanelExecutionError("executor entrypoint bytes differ from frozen manifest")
    argv = doc.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise FrozenPanelExecutionError("frozen executor argv malformed")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv):
        raise FrozenPanelExecutionError("frozen executor argv contains forbidden control characters")
    if entrypoint_rel not in argv:
        raise FrozenPanelExecutionError("frozen executor argv lost entrypoint identity")
    try:
        timeout = float(doc.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError("executor timeout is not numeric") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise FrozenPanelExecutionError("executor timeout must be finite and > 0")
    allowed = doc.get("allowed_environment_variables")
    if (
        not isinstance(allowed, list)
        or not all(isinstance(x, str) and x.strip() and "=" not in x for x in allowed)
        or [x.strip() for x in allowed] != sorted(set(x.strip() for x in allowed))
    ):
        raise FrozenPanelExecutionError("executor environment allow-list malformed")
    return doc, tuple(argv), timeout


def _pricing_rate_cards(
    root: Path,
    execution: Mapping[str, object],
) -> tuple[dict[tuple[str, str, str], ProviderRateCard], str]:
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise FrozenPanelExecutionError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "pricing_snapshot"
    ]
    if len(matches) != 1:
        raise FrozenPanelExecutionError("exactly one frozen pricing snapshot is required")
    component = matches[0]
    path, _ = _safe_repo_file(root, component.get("path"))
    component_sha = _sha("pricing snapshot component sha256", component.get("sha256"))
    if sha256_file(path) != component_sha:
        raise FrozenPanelExecutionError("pricing snapshot bytes differ from execution freeze")
    doc = _json(path, schema="DGC_PRICING_SNAPSHOT_V1")
    captured_at = str(doc.get("captured_at", "")).strip()
    entries = doc.get("entries")
    if not captured_at or not isinstance(entries, list) or not entries:
        raise FrozenPanelExecutionError("frozen pricing snapshot is incomplete")
    cards: dict[tuple[str, str, str], ProviderRateCard] = {}
    try:
        for row in entries:
            if not isinstance(row, Mapping):
                raise FrozenPanelExecutionError("invalid frozen pricing row")
            identity = (
                str(row["provider"]).strip(),
                str(row["model_id"]).strip(),
                str(row["model_version"]).strip(),
            )
            if not all(identity) or identity in cards:
                raise FrozenPanelExecutionError("duplicate/empty frozen pricing identity")
            if str(row.get("currency", "")) != "USD":
                raise FrozenPanelExecutionError("frozen pricing currency must be USD")
            cards[identity] = ProviderRateCard(
                provider=identity[0],
                model=identity[1],
                input_usd_per_million=float(row["input_per_million"]),
                cached_input_usd_per_million=float(row["cached_input_per_million"]),
                cache_write_usd_per_million=float(row["cache_write_per_million"]),
                long_cache_write_usd_per_million=float(row["long_cache_write_per_million"]),
                output_usd_per_million=float(row["output_per_million"]),
                source_uri=str(row["source_uri"]),
                retrieved_at=captured_at,
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError("invalid frozen pricing rate card") from exc
    return cards, component_sha


def _provider_model_meter(
    *,
    response: Mapping[str, object],
    unit: WorkUnitId,
    rate_cards: Mapping[tuple[str, str, str], ProviderRateCard],
) -> tuple[float, str, tuple[dict[str, object], ...]]:
    raw_rows = response.get("provider_usage_traces")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise FrozenPanelExecutionError("executor response requires provider_usage_traces")
    trace_docs: list[dict[str, object]] = []
    metered_rows: list[tuple[str, str]] = []
    request_ids: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise FrozenPanelExecutionError("invalid provider usage trace row")
        model_version = str(raw.get("model_version", "")).strip()
        identity = (
            str(raw.get("provider", "")).strip(),
            str(raw.get("model", "")).strip(),
            model_version,
        )
        card = rate_cards.get(identity)
        if card is None:
            raise FrozenPanelExecutionError("provider usage trace has no exact frozen rate card")
        try:
            trace = ProviderUsageTrace(
                trace_id=str(raw["trace_id"]),
                decision_id=str(raw["decision_id"]),
                policy_id=str(raw["policy_id"]),
                authority=TraceAuthority(str(raw["authority"])),
                provider=identity[0],
                model=identity[1],
                rate_card_digest=str(raw["rate_card_digest"]),
                input_tokens=int(raw["input_tokens"]),
                cached_input_tokens=int(raw.get("cached_input_tokens", 0)),
                cache_write_tokens=int(raw.get("cache_write_tokens", 0)),
                long_cache_write_tokens=int(raw.get("long_cache_write_tokens", 0)),
                output_tokens=int(raw["output_tokens"]),
                provider_request_id=str(raw["provider_request_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FrozenPanelExecutionError("malformed provider usage trace") from exc
        if trace.authority is not TraceAuthority.PROVIDER_LIVE:
            raise FrozenPanelExecutionError("confirmatory provider usage must be PROVIDER_LIVE")
        if trace.decision_id != unit.stable_id or trace.policy_id != unit.policy_id:
            raise FrozenPanelExecutionError("provider trace decision/policy identity mismatch")
        if trace.rate_card_digest != card.digest:
            raise FrozenPanelExecutionError("provider trace rate-card digest mismatch")
        request_id = str(trace.provider_request_id)
        if request_id in request_ids:
            raise FrozenPanelExecutionError("duplicate provider_request_id in one work unit")
        request_ids.add(request_id)
        metered = trace.meter(card)
        trace_doc = {
            "trace_digest": trace.digest,
            "trace_id": trace.trace_id,
            "provider_request_id": trace.provider_request_id,
            "provider": trace.provider,
            "model": trace.model,
            "model_version": model_version,
            "rate_card_digest": trace.rate_card_digest,
            "input_tokens": trace.input_tokens,
            "cached_input_tokens": trace.cached_input_tokens,
            "cache_write_tokens": trace.cache_write_tokens,
            "long_cache_write_tokens": trace.long_cache_write_tokens,
            "output_tokens": trace.output_tokens,
            "model_token_usd": metered.model_token_usd,
        }
        trace_docs.append(trace_doc)
        metered_rows.append((trace.digest, model_version))
    population_digest = sha256_bytes(canonical_json_bytes(sorted(metered_rows)))
    return math.fsum([float(row["model_token_usd"]) for row in trace_docs]), population_digest, tuple(trace_docs)


def _risk_endpoint_manifest(
    root: Path,
    execution: Mapping[str, object],
) -> tuple[dict[str, object], tuple[str, ...], float, str]:
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise FrozenPanelExecutionError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "risk_endpoint_manifest"
    ]
    if len(matches) != 1:
        raise FrozenPanelExecutionError("exactly one frozen risk endpoint manifest is required")
    row = matches[0]
    manifest_path, _ = _safe_repo_file(root, row.get("path"))
    component_sha = _sha("risk endpoint component sha256", row.get("sha256"))
    if sha256_file(manifest_path) != component_sha:
        raise FrozenPanelExecutionError("risk endpoint manifest bytes differ from execution freeze")
    doc = _json(manifest_path, schema="DGC_RISK_ENDPOINT_MANIFEST_V1")
    if doc.get("protocol") != RISK_ENDPOINT_PROTOCOL:
        raise FrozenPanelExecutionError("risk endpoint protocol identity mismatch")
    if (
        doc.get("request_schema") != RISK_ENDPOINT_REQUEST_SCHEMA
        or doc.get("response_schema") != RISK_ENDPOINT_RESPONSE_SCHEMA
    ):
        raise FrozenPanelExecutionError("risk endpoint request/response schema identity mismatch")
    implementation, implementation_rel = _safe_repo_file(root, doc.get("implementation_path"))
    if sha256_file(implementation) != _sha(
        "risk endpoint implementation sha256", doc.get("implementation_sha256")
    ):
        raise FrozenPanelExecutionError("risk endpoint implementation bytes differ from frozen manifest")
    argv = doc.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise FrozenPanelExecutionError("frozen risk endpoint argv malformed")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv):
        raise FrozenPanelExecutionError("frozen risk endpoint argv contains forbidden control characters")
    if implementation_rel not in argv:
        raise FrozenPanelExecutionError("frozen risk endpoint argv lost implementation identity")
    try:
        timeout = float(doc.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError("risk endpoint timeout is not numeric") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise FrozenPanelExecutionError("risk endpoint timeout must be finite and > 0")
    if doc.get("network_access_allowed") is not False:
        raise FrozenPanelExecutionError("risk endpoint must remain network-disabled")
    return doc, tuple(argv), timeout, component_sha


def _runtime_env(root: Path, materialization_root: Path, executor: Mapping[str, object]) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "PYTHONHASHSEED": "0",
        "DGC_REPOSITORY_ROOT": str(root),
        "DGC_MATERIALIZATION_ROOT": str(materialization_root),
    }
    for raw in executor.get("allowed_environment_variables", []):
        name = str(raw)
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _risk_runtime_env(root: Path, materialization_root: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "PYTHONHASHSEED": "0",
        "DGC_REPOSITORY_ROOT": str(root),
        "DGC_MATERIALIZATION_ROOT": str(materialization_root),
    }


def _invoke_risk_endpoint(
    *,
    manifest: Mapping[str, object],
    argv: Sequence[str],
    timeout: float,
    adapter_response: Mapping[str, object],
    unit_request: Mapping[str, object],
    root: Path,
    env: Mapping[str, str],
) -> tuple[dict[str, object], bytes, bytes]:
    request = {
        "schema": RISK_ENDPOINT_REQUEST_SCHEMA,
        "endpoint_name": manifest["endpoint_name"],
        "semantics_version": manifest["semantics_version"],
        "source_fields": manifest["source_fields"],
        "unit": unit_request["unit"],
        "attempt": unit_request["attempt"],
        "adapter_response": dict(adapter_response),
    }
    raw_request = canonical_json_bytes(request) + b"\n"
    try:
        proc = subprocess.run(
            list(argv),
            cwd=root,
            env=dict(env),
            input=raw_request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FrozenPanelExecutionError("frozen risk endpoint timed out") from exc
    except OSError as exc:
        raise FrozenPanelExecutionError("frozen risk endpoint could not start") from exc
    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise FrozenPanelExecutionError(f"frozen risk endpoint exited nonzero: {proc.returncode}")
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenPanelExecutionError("risk endpoint stdout is not one JSON response") from exc
    if not isinstance(response, dict) or response.get("schema") != RISK_ENDPOINT_RESPONSE_SCHEMA:
        raise FrozenPanelExecutionError("risk endpoint response schema mismatch")
    evidence = response.get("evidence")
    if not isinstance(evidence, Mapping) or not evidence:
        raise FrozenPanelExecutionError("risk endpoint response requires non-empty evidence")
    _finite_probability("catastrophic_regret", response.get("catastrophic_regret"))
    return response, stdout, stderr


def _finite_probability(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0 or result > 1:
        raise FrozenPanelExecutionError(f"{name} must be finite in [0,1]")
    return result


def _finite_cost(value: object, *, cap: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError("actual_cost_usd must be numeric") from exc
    if not math.isfinite(result) or result < 0 or result > cap + 1e-12:
        raise FrozenPanelExecutionError("actual_cost_usd outside frozen per-unit cap")
    return result


def _physical_cost_certificate(
    *,
    response: Mapping[str, object],
    trial_id: str,
    cap: float,
    model_usd: float,
    model_source_digest: str,
) -> PhysicalCostCertificate:
    raw = response.get("physical_cost_evidence")
    if not isinstance(raw, Mapping):
        raise FrozenPanelExecutionError("executor response requires physical_cost_evidence")
    adapter_components = set(PRODUCT_COST_COMPONENTS) - {"model_usd"}
    if set(str(key) for key in raw) != adapter_components:
        raise FrozenPanelExecutionError(
            "physical_cost_evidence must cover exact non-model product cost components"
        )
    evidence: dict[str, CostComponentEvidence] = {
        "model_usd": CostComponentEvidence(
            component="model_usd",
            value_usd=model_usd,
            authority=CostAuthority.PROVIDER_METER,
            source_digest=model_source_digest,
        )
    }
    try:
        for component in PRODUCT_COST_COMPONENTS:
            if component == "model_usd":
                continue
            row = raw[component]
            if not isinstance(row, Mapping):
                raise FrozenPanelExecutionError(f"invalid physical cost evidence row: {component}")
            authority = CostAuthority(str(row.get("authority")))
            evidence[component] = CostComponentEvidence(
                component=component,
                value_usd=float(row.get("value_usd")),
                authority=authority,
                source_digest=_sha(
                    f"physical cost source digest {component}", row.get("source_digest")
                ),
            )
        certificate = certify_physical_trial_cost(trial_id=trial_id, evidence=evidence)
    except (TypeError, ValueError, KeyError) as exc:
        raise FrozenPanelExecutionError("invalid physical cost evidence") from exc
    total = certificate.cost.total_operational_usd
    if total > cap + 1e-12:
        raise FrozenPanelExecutionError("certified physical cost exceeds frozen per-unit cap")
    declared = response.get("actual_cost_usd")
    if declared is not None:
        try:
            declared_value = float(declared)
        except (TypeError, ValueError) as exc:
            raise FrozenPanelExecutionError("declared actual_cost_usd must be numeric") from exc
        if not math.isfinite(declared_value) or not math.isclose(
            declared_value, total, rel_tol=0.0, abs_tol=1e-12
        ):
            raise FrozenPanelExecutionError("declared actual_cost_usd differs from certified physical cost")
    return certificate

def _policy_subject(root: Path, execution: Mapping[str, object], policy_id: str) -> dict[str, object]:
    policies = execution.get("governance_policies")
    if not isinstance(policies, list):
        raise FrozenPanelExecutionError("frozen governance policy population missing")
    matches = [
        row for row in policies
        if isinstance(row, Mapping) and str(row.get("policy_id")) == policy_id
    ]
    if len(matches) != 1:
        raise FrozenPanelExecutionError("work unit policy lacks one frozen governance manifest")
    row = dict(matches[0])
    manifest_path, manifest_rel = _safe_repo_file(root, row.get("path"))
    if sha256_file(manifest_path) != _sha("governance policy manifest sha256", row.get("sha256")):
        raise FrozenPanelExecutionError("governance policy manifest bytes differ from execution freeze")
    manifest = _json(manifest_path, schema="DGC_GOVERNANCE_POLICY_MANIFEST_V1")
    if str(manifest.get("policy_id", "")) != policy_id:
        raise FrozenPanelExecutionError("governance policy manifest id mismatch")
    for kind in ("implementation", "config"):
        path_key = f"{kind}_path"
        sha_key = f"{kind}_sha256"
        subject, subject_rel = _safe_repo_file(root, manifest.get(path_key))
        declared = _sha(f"governance {kind} sha256", manifest.get(sha_key))
        if sha256_file(subject) != declared:
            raise FrozenPanelExecutionError(f"governance {kind} bytes differ from frozen manifest")
        if row.get(path_key) != subject_rel or row.get(sha_key) != declared:
            raise FrozenPanelExecutionError(f"governance {kind} lineage differs from execution freeze")
    if row.get("path") != manifest_rel:
        raise FrozenPanelExecutionError("governance policy path is non-canonical")
    return row


def _request(
    *,
    repository_root: Path,
    execution: Mapping[str, object],
    root_authority: Mapping[str, object],
    lease: Lease,
) -> dict[str, object]:
    components = execution.get("components")
    if not isinstance(components, list):
        raise FrozenPanelExecutionError("frozen execution component population missing")
    policy = _policy_subject(
        root=repository_root,
        execution=execution,
        policy_id=lease.unit.policy_id,
    )
    return {
        "schema": EXECUTOR_REQUEST_SCHEMA,
        "family_id": root_authority["family_id"],
        "generation_id": root_authority["generation_id"],
        "root_authority_digest": root_authority["authority_digest"],
        "root_digest": root_authority["root_digest"],
        "distributed_spec_digest": root_authority["distributed_spec_digest"],
        "materialization_reference_digest": execution["materialization_reference_digest"],
        "unit": asdict(lease.unit),
        "attempt": lease.attempt,
        "frozen_components": components,
        "governance_policy": policy,
    }


def _invoke(
    *,
    argv: Sequence[str],
    request: Mapping[str, object],
    root: Path,
    env: Mapping[str, str],
    timeout: float,
) -> tuple[dict[str, object], bytes, bytes]:
    raw_request = canonical_json_bytes(dict(request)) + b"\n"
    try:
        proc = subprocess.run(
            list(argv),
            cwd=root,
            env=dict(env),
            input=raw_request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FrozenPanelExecutionError("frozen unit executor timed out") from exc
    except OSError as exc:
        raise FrozenPanelExecutionError("frozen unit executor could not start") from exc
    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise FrozenPanelExecutionError(f"frozen unit executor exited nonzero: {proc.returncode}")
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenPanelExecutionError("executor stdout is not one JSON response") from exc
    if not isinstance(response, dict) or response.get("schema") != EXECUTOR_RESPONSE_SCHEMA:
        raise FrozenPanelExecutionError("executor response schema mismatch")
    if response.get("unit") != request.get("unit"):
        raise FrozenPanelExecutionError("executor response unit differs from frozen request")
    if int(response.get("attempt", -1)) != int(request.get("attempt", -2)):
        raise FrozenPanelExecutionError("executor response attempt differs from lease")
    trace = response.get("trace")
    if not isinstance(trace, Mapping) or not trace:
        raise FrozenPanelExecutionError("executor response requires non-empty raw trace metadata")
    return response, stdout, stderr


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(dict(payload), indent=2, sort_keys=True).encode("utf-8") + b"\n")


def _audit_document(coordinator: DistributedEvalCoordinator, spec: DistributedEvalSpec) -> dict[str, object]:
    events = [asdict(event) for event in coordinator.audit_events()]
    if not events:
        raise FrozenPanelExecutionError("execution produced no coordinator audit events")
    audit_root = events[-1]["event_digest"]
    payload = {"spec_digest": spec.digest, "events": events, "audit_root_digest": audit_root}
    return {
        "schema": AUDIT_SCHEMA,
        **payload,
        "audit_log_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def execute_frozen_panel(
    *,
    repository_root: Path,
    execution_manifest_freeze_path: Path,
    harness_freeze_path: Path,
    confirmatory_root_authority_path: Path,
    materialization_generation_root: Path,
    source_registry_path: Path,
    output_root: Path,
    worker_id: str = "dgc-local-executor",
) -> Path:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise FrozenPanelExecutionError("repository root missing")
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    execution_digest = _sha("execution freeze digest", execution.get("freeze_digest"))
    harness_digest = _sha("harness freeze digest", harness.get("harness_freeze_digest"))
    if authority.get("execution_manifest_freeze_digest") != execution_digest:
        raise FrozenPanelExecutionError("confirmatory root execution-freeze lineage mismatch")
    if authority.get("harness_freeze_digest") != harness_digest:
        raise FrozenPanelExecutionError("confirmatory root harness lineage mismatch")
    if harness.get("execution_manifest_freeze_digest") != execution_digest:
        raise FrozenPanelExecutionError("harness execution-freeze lineage mismatch")
    family = str(authority.get("family_id", ""))
    if family != str(execution.get("family_id", "")) or family != str(harness.get("family_id", "")):
        raise FrozenPanelExecutionError("execution family lineage mismatch")

    _assert_git_identity(root, execution)
    reference = verify_materialization_generation(
        Path(materialization_generation_root),
        expected_repository_commit=str(execution["repository_commit"]),
        expected_repository_tree=str(execution["repository_tree"]),
        source_registry_path=Path(source_registry_path),
    )
    if reference.digest != _sha("materialization reference digest", execution.get("materialization_reference_digest")):
        raise FrozenPanelExecutionError("materialized bytes differ from frozen execution reference")
    if reference.binding(family).materialized_task_manifest_sha256 != execution.get("task_manifest_digest"):
        raise FrozenPanelExecutionError("materialized task population differs from execution freeze")

    executor, argv, timeout = _executor_manifest(root, execution)
    rate_cards, pricing_component_sha = _pricing_rate_cards(root, execution)
    risk_endpoint, risk_argv, risk_timeout, risk_component_sha = _risk_endpoint_manifest(root, execution)
    try:
        spec = DistributedEvalSpec(**dict(authority["distributed_spec"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenPanelExecutionError("distributed spec cannot be reconstructed") from exc
    if spec.digest != authority.get("distributed_spec_digest"):
        raise FrozenPanelExecutionError("distributed spec digest mismatch")
    coordinator = DistributedEvalCoordinator(spec)

    final = Path(output_root)
    if final.exists():
        raise FileExistsError("execution bundle output is immutable")
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{final.name}.staging-", dir=final.parent))
    tick = 0
    result_paths: list[str] = []
    result_index = 0
    try:
        materialization_root = Path(materialization_generation_root).resolve()
        env = _runtime_env(root, materialization_root, executor)
        risk_env = _risk_runtime_env(root, materialization_root)
        while True:
            lease = coordinator.claim(worker_id, tick=tick)
            if lease is None:
                snapshot = coordinator.snapshot(tick=tick)
                counts = snapshot["counts"]
                if counts.get("COMMITTED") == len(spec.units()):
                    break
                raise FrozenPanelExecutionError(f"executor cannot claim remaining frozen units: {counts}")
            tick += 1
            request = _request(
                repository_root=root,
                execution=execution,
                root_authority=authority,
                lease=lease,
            )
            attempt_id = hashlib.sha256(
                f"{lease.unit.stable_id}::{lease.attempt}".encode("utf-8")
            ).hexdigest()[:24]
            transcript_dir = staging / "transcripts" / attempt_id
            transcript_dir.mkdir(parents=True, exist_ok=True)
            try:
                response, stdout, stderr = _invoke(
                    argv=argv, request=request, root=root, env=env, timeout=timeout
                )
                quality = _finite_probability("quality", response.get("quality"))
                model_usd, provider_trace_population_digest, provider_trace_docs = _provider_model_meter(
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
                risk_response, risk_stdout, risk_stderr = _invoke_risk_endpoint(
                    manifest=risk_endpoint,
                    argv=risk_argv,
                    timeout=risk_timeout,
                    adapter_response=response,
                    unit_request=request,
                    root=root,
                    env=risk_env,
                )
                regret = _finite_probability(
                    "catastrophic_regret", risk_response.get("catastrophic_regret")
                )
            except FrozenPanelExecutionError as exc:
                (transcript_dir / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
                tick = max(tick, lease.expires_tick)
                coordinator.snapshot(tick=tick)
                continue

            stdout_path = transcript_dir / "stdout.bin"
            stderr_path = transcript_dir / "stderr.bin"
            risk_stdout_path = transcript_dir / "risk-stdout.bin"
            risk_stderr_path = transcript_dir / "risk-stderr.bin"
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)
            risk_stdout_path.write_bytes(risk_stdout)
            risk_stderr_path.write_bytes(risk_stderr)
            response_digest = sha256_bytes(canonical_json_bytes(response))
            trace_digest = sha256_bytes(canonical_json_bytes(response["trace"]))
            risk_response_digest = sha256_bytes(canonical_json_bytes(risk_response))
            evidence_rel = f"evidence/{result_index:08d}.json"
            evidence_path = staging / evidence_rel
            evidence_doc = {
                "schema": EVIDENCE_SCHEMA,
                "request": request,
                "response": response,
                "executor_manifest_sha256": next(
                    row["sha256"] for row in execution["components"]
                    if isinstance(row, Mapping) and row.get("component") == "executor_manifest"
                ),
                "executor_entrypoint_sha256": executor["entrypoint_sha256"],
                "argv": list(argv),
                "stdout_path": stdout_path.relative_to(staging).as_posix(),
                "stdout_sha256": sha256_file(stdout_path),
                "stderr_path": stderr_path.relative_to(staging).as_posix(),
                "stderr_sha256": sha256_file(stderr_path),
                "adapter_response_digest": response_digest,
                "trace_digest": trace_digest,
                "risk_endpoint_manifest_sha256": risk_component_sha,
                "risk_endpoint_implementation_sha256": risk_endpoint["implementation_sha256"],
                "risk_endpoint_response": risk_response,
                "risk_endpoint_response_digest": risk_response_digest,
                "risk_stdout_path": risk_stdout_path.relative_to(staging).as_posix(),
                "risk_stdout_sha256": sha256_file(risk_stdout_path),
                "risk_stderr_path": risk_stderr_path.relative_to(staging).as_posix(),
                "risk_stderr_sha256": sha256_file(risk_stderr_path),
                "pricing_snapshot_manifest_sha256": pricing_component_sha,
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
                "catastrophic_regret": regret,
                "adapter_response_digest": response_digest,
                "trace_digest": trace_digest,
                "risk_endpoint_response_digest": risk_response_digest,
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
                raise FrozenPanelExecutionError("coordinator rejected executor result") from exc
            record_payload = {
                "root_authority_digest": authority["authority_digest"],
                "root_digest": authority["root_digest"],
                "distributed_spec_digest": spec.digest,
                "unit": asdict(record.unit),
                "attempt": record.attempt,
                "worker_id": record.worker_id,
                "committed_tick": record.committed_tick,
                "result_payload": result_payload,
                "result_digest": canonical_result_payload_digest(result_payload),
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
            raise FrozenPanelExecutionError("coordinator audit chain failed self-verification")
        _write_json(staging / "AUDIT_LOG.json", _audit_document(coordinator, spec))
        rows = file_manifest(staging, excluded_names=frozenset({"EXECUTION_BUNDLE.json"}))
        payload_manifest = sha256_bytes(canonical_json_bytes(rows))
        manifest_payload = {
            "family_id": family,
            "root_authority_digest": authority["authority_digest"],
            "root_digest": authority["root_digest"],
            "distributed_spec_digest": spec.digest,
            "payload_manifest_sha256": payload_manifest,
            "audit_log_path": "AUDIT_LOG.json",
            "result_paths": result_paths,
            "expected_units": completion.expected_units,
            "committed_units": completion.committed_units,
            "audit_root_digest": completion.audit_root_digest,
            "result_population_digest": completion.result_population_digest,
            "total_cost_usd": completion.total_cost_usd,
            "product_promotion_authorized": False,
        }
        _write_json(staging / "EXECUTION_BUNDLE.json", {
            "schema": BUNDLE_SCHEMA,
            **manifest_payload,
            "bundle_digest": sha256_bytes(canonical_json_bytes(manifest_payload)),
        })
        verify_execution_bundle(
            staging,
            confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        )
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
