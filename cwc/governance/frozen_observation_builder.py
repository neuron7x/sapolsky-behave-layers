from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.execution_manifest_freeze import (
    OBSERVATION_BUILDER_PROTOCOL,
    OBSERVATION_REQUEST_SCHEMA,
    OBSERVATION_RESPONSE_SCHEMA,
    policy_observation_contract_digest,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file

NETWORK_ISOLATOR = ("unshare", "--net", "--")
_FORBIDDEN_METADATA_KEYS = frozenset({
    "accepted_success",
    "catastrophic_regret",
    "confirmatory_label",
    "final_reward",
    "ground_truth",
    "reward",
    "test_outcome",
    "verifier_result",
})


class FrozenObservationBuilderError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenObservationBuilderError(f"{name} must be lowercase SHA-256")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FrozenObservationBuilderError("observation subject path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise FrozenObservationBuilderError(
                f"observation subject symlink rejected: {rel.as_posix()}"
            )
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FrozenObservationBuilderError("observation subject escapes repository root") from exc
    if not resolved.is_file():
        raise FrozenObservationBuilderError(f"observation subject missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenObservationBuilderError(f"invalid JSON subject: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise FrozenObservationBuilderError(f"unexpected observation schema: {path}")
    return payload


def _canonical_mapping(name: str, value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise FrozenObservationBuilderError(f"{name} must be a mapping")
    payload = {str(key): item for key, item in value.items()}
    try:
        canonical_json_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise FrozenObservationBuilderError(f"{name} must be canonical-JSON serializable") from exc
    return payload


def _finite_observations(
    *,
    expected_fields: Sequence[str],
    observed: object,
) -> dict[str, float]:
    if not isinstance(observed, Mapping):
        raise FrozenObservationBuilderError("observation response must contain a mapping")
    payload = {str(key): value for key, value in observed.items()}
    if sorted(payload) != list(expected_fields):
        raise FrozenObservationBuilderError(
            f"observation response fields differ from frozen contract; "
            f"expected={list(expected_fields)}; observed={sorted(payload)}"
        )
    clean: dict[str, float] = {}
    for field in expected_fields:
        raw = payload[field]
        if isinstance(raw, bool):
            raise FrozenObservationBuilderError(f"observation {field} must be numeric, not boolean")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise FrozenObservationBuilderError(f"observation {field} must be numeric") from exc
        if not math.isfinite(value):
            raise FrozenObservationBuilderError(f"observation {field} must be finite")
        clean[field] = value
    return clean


@dataclass(frozen=True, slots=True)
class FrozenObservationResult:
    mode: str
    observations: dict[str, float]
    request_digest: str
    response_digest: str
    stdout_sha256: str
    stderr_sha256: str
    trace: dict[str, object]
    common_probe_required: bool = False
    product_promotion_authorized: bool = False

    @property
    def document(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "observations": self.observations,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "trace": self.trace,
            "common_probe_required": self.common_probe_required,
            "product_promotion_authorized": False,
        }


def load_frozen_observation_builder(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], tuple[str, ...], float]:
    root = Path(repository_root).resolve()
    rows = execution_freeze.get("components")
    if not isinstance(rows, list):
        raise FrozenObservationBuilderError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "observation_builder_manifest"
    ]
    if len(matches) != 1:
        raise FrozenObservationBuilderError("exactly one frozen observation builder required")
    row = matches[0]
    manifest_path, manifest_rel = _safe_file(root, row.get("path"))
    component_sha = _sha("observation builder component sha256", row.get("sha256"))
    if sha256_file(manifest_path) != component_sha:
        raise FrozenObservationBuilderError("observation builder manifest bytes differ from freeze")
    if manifest_rel != row.get("path"):
        raise FrozenObservationBuilderError("observation builder manifest path is non-canonical")
    manifest = _json(manifest_path, schema="DGC_OBSERVATION_BUILDER_MANIFEST_V1")
    if manifest.get("protocol") != OBSERVATION_BUILDER_PROTOCOL:
        raise FrozenObservationBuilderError("observation builder protocol mismatch")
    if manifest.get("request_schema") != OBSERVATION_REQUEST_SCHEMA:
        raise FrozenObservationBuilderError("observation builder request schema mismatch")
    if manifest.get("response_schema") != OBSERVATION_RESPONSE_SCHEMA:
        raise FrozenObservationBuilderError("observation builder response schema mismatch")
    if manifest.get("confirmatory_label_access") is not False:
        raise FrozenObservationBuilderError("observation builder confirmatory-label access must be false")
    if manifest.get("post_outcome_feature_mutation_allowed") is not False:
        raise FrozenObservationBuilderError("post-outcome observation mutation must be false")

    implementation, implementation_rel = _safe_file(root, manifest.get("implementation_path"))
    config_path, config_rel = _safe_file(root, manifest.get("config_path"))
    if sha256_file(implementation) != _sha(
        "observation implementation sha256", manifest.get("implementation_sha256")
    ):
        raise FrozenObservationBuilderError("observation implementation bytes differ from manifest")
    if sha256_file(config_path) != _sha(
        "observation config sha256", manifest.get("config_sha256")
    ):
        raise FrozenObservationBuilderError("observation config bytes differ from manifest")
    config = _json(config_path, schema="DGC_OBSERVATION_BUILDER_CONFIG_V1")
    for field in ("mode", "observation_fields", "probe_action_id"):
        if config.get(field) != manifest.get(field):
            raise FrozenObservationBuilderError(
                f"observation builder config {field} differs from manifest"
            )

    fields = manifest.get("observation_fields")
    digest = policy_observation_contract_digest(fields)
    if not isinstance(fields, list):
        raise FrozenObservationBuilderError("observation fields missing")
    expected_fields = tuple(str(item).strip() for item in fields)
    if digest != policy_observation_contract_digest(list(expected_fields)):
        raise FrozenObservationBuilderError("observation contract digest is unstable")

    argv = manifest.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item.strip() for item in argv):
        raise FrozenObservationBuilderError("observation builder argv malformed")
    if implementation_rel not in argv or config_rel not in argv:
        raise FrozenObservationBuilderError("observation builder argv lost implementation/config identity")
    try:
        timeout = float(manifest.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise FrozenObservationBuilderError("observation builder timeout malformed") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise FrozenObservationBuilderError("observation builder timeout must be finite and > 0")
    return manifest, config, tuple(argv), timeout


def build_frozen_observations(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    family_id: str,
    task_id: str,
    replicate: int,
    task_metadata: Mapping[str, object],
) -> FrozenObservationResult:
    root = Path(repository_root).resolve()
    manifest, _, argv, timeout = load_frozen_observation_builder(
        repository_root=root,
        execution_freeze=execution_freeze,
    )
    mode = str(manifest.get("mode", ""))
    if mode == "COMMON_MODEL_PROBE_V1":
        raise FrozenObservationBuilderError(
            "COMMON_MODEL_PROBE_REQUIRES_WORKLOAD_ADAPTER: provider/tool usage and "
            "probe cost must be source-bound and charged identically to every arm"
        )
    if mode != "STATIC_ONLY_V1":
        raise FrozenObservationBuilderError("unsupported observation builder runtime mode")
    if manifest.get("network_access_allowed") is not False:
        raise FrozenObservationBuilderError("static observation builder must prohibit network access")

    family = str(family_id).strip()
    task = str(task_id).strip()
    if not family or not task:
        raise FrozenObservationBuilderError("family_id and task_id required")
    if isinstance(replicate, bool) or int(replicate) < 0:
        raise FrozenObservationBuilderError("replicate must be a nonnegative integer")
    metadata = _canonical_mapping("task_metadata", task_metadata)
    leaked = sorted(set(metadata) & _FORBIDDEN_METADATA_KEYS)
    if leaked:
        raise FrozenObservationBuilderError(
            f"task metadata contains forbidden outcome fields: {leaked}"
        )

    request = {
        "schema": OBSERVATION_REQUEST_SCHEMA,
        "family_id": family,
        "task_id": task,
        "replicate": int(replicate),
        "task_metadata": metadata,
        "mode": mode,
        "observation_fields": manifest["observation_fields"],
    }
    raw_request = canonical_json_bytes(request) + b"\n"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "PYTHONHASHSEED": "0",
    }
    command: Sequence[str] = (*NETWORK_ISOLATOR, *argv)
    try:
        proc = subprocess.run(
            list(command),
            cwd=root,
            env=env,
            input=raw_request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FrozenObservationBuilderError("observation builder timed out") from exc
    except OSError as exc:
        raise FrozenObservationBuilderError(
            "observation builder could not start with network isolation"
        ) from exc
    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise FrozenObservationBuilderError(
            f"observation builder exited nonzero: {proc.returncode}"
        )
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenObservationBuilderError(
            "observation builder stdout is not one JSON response"
        ) from exc
    if not isinstance(response, dict) or response.get("schema") != OBSERVATION_RESPONSE_SCHEMA:
        raise FrozenObservationBuilderError("observation builder response schema mismatch")
    observations = _finite_observations(
        expected_fields=tuple(str(x) for x in manifest["observation_fields"]),
        observed=response.get("observations"),
    )
    trace = _canonical_mapping("observation trace", response.get("trace"))
    if not trace:
        raise FrozenObservationBuilderError("observation builder response requires non-empty trace")
    return FrozenObservationResult(
        mode=mode,
        observations=observations,
        request_digest=hashlib.sha256(canonical_json_bytes(request)).hexdigest(),
        response_digest=hashlib.sha256(canonical_json_bytes(response)).hexdigest(),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        trace=trace,
    )
