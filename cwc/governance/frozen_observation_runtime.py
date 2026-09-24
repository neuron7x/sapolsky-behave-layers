from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.execution_manifest_freeze import (
    OBSERVATION_PROVIDER_PROTOCOL,
    OBSERVATION_PROVIDER_REQUEST_SCHEMA,
    OBSERVATION_PROVIDER_RESPONSE_SCHEMA,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file

NETWORK_ISOLATOR = ("unshare", "--net", "--")


class FrozenObservationRuntimeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenObservationRuntimeError(f"{name} must be lowercase SHA-256")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FrozenObservationRuntimeError("observation provider path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise FrozenObservationRuntimeError(
                f"observation provider symlink path rejected: {rel.as_posix()}"
            )
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FrozenObservationRuntimeError(
            "observation provider path escapes repository root"
        ) from exc
    if not resolved.is_file():
        raise FrozenObservationRuntimeError("observation provider subject missing")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenObservationRuntimeError("invalid observation provider JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise FrozenObservationRuntimeError("unexpected observation provider schema")
    return payload


@dataclass(frozen=True, slots=True)
class FrozenObservationResult:
    observations: dict[str, object]
    output_fields: tuple[str, ...]
    source_manifest_digest: str
    request_digest: str
    response_digest: str
    stdout_sha256: str
    stderr_sha256: str
    component_sha256: str
    implementation_sha256: str
    network_isolation: str = "LINUX_UNSHARE_NET_V1"

    @property
    def document(self) -> dict[str, object]:
        return {
            "observations": self.observations,
            "output_fields": list(self.output_fields),
            "source_manifest_digest": self.source_manifest_digest,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "component_sha256": self.component_sha256,
            "implementation_sha256": self.implementation_sha256,
            "network_isolation": self.network_isolation,
        }


def invoke_frozen_observation_provider(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    materialization_root: Path,
    family_id: str,
    task_id: str,
    budget_remaining: object,
    step_index: object,
) -> FrozenObservationResult:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise FrozenObservationRuntimeError("repository root missing")
    materialization = Path(materialization_root).resolve()
    if not materialization.is_dir():
        raise FrozenObservationRuntimeError("materialization root missing")

    components = execution_freeze.get("components")
    if not isinstance(components, list):
        raise FrozenObservationRuntimeError("execution component population missing")
    matches = [
        row for row in components
        if isinstance(row, Mapping)
        and row.get("component") == "observation_provider_manifest"
    ]
    if len(matches) != 1:
        raise FrozenObservationRuntimeError(
            "exactly one frozen observation provider component required"
        )
    row = dict(matches[0])
    manifest_path, manifest_rel = _safe_file(root, row.get("path"))
    component_sha = _sha("observation provider component sha256", row.get("sha256"))
    if sha256_file(manifest_path) != component_sha:
        raise FrozenObservationRuntimeError(
            "observation provider manifest bytes differ from execution freeze"
        )
    if manifest_rel != row.get("path"):
        raise FrozenObservationRuntimeError("observation provider path is non-canonical")

    manifest = _json(
        manifest_path, schema="DGC_OBSERVATION_PROVIDER_MANIFEST_V1"
    )
    if manifest.get("protocol") != OBSERVATION_PROVIDER_PROTOCOL:
        raise FrozenObservationRuntimeError("observation provider protocol mismatch")
    if manifest.get("request_schema") != OBSERVATION_PROVIDER_REQUEST_SCHEMA:
        raise FrozenObservationRuntimeError("observation provider request schema mismatch")
    if manifest.get("response_schema") != OBSERVATION_PROVIDER_RESPONSE_SCHEMA:
        raise FrozenObservationRuntimeError("observation provider response schema mismatch")
    if manifest.get("network_access_allowed") is not False:
        raise FrozenObservationRuntimeError("observation provider network access must be false")
    if manifest.get("confirmatory_label_access") is not False:
        raise FrozenObservationRuntimeError("observation provider label access must be false")
    if manifest.get("post_outcome_access_allowed") is not False:
        raise FrozenObservationRuntimeError("observation provider post-outcome access must be false")

    implementation, implementation_rel = _safe_file(
        root, manifest.get("implementation_path")
    )
    implementation_sha = _sha(
        "observation provider implementation sha256",
        manifest.get("implementation_sha256"),
    )
    if sha256_file(implementation) != implementation_sha:
        raise FrozenObservationRuntimeError(
            "observation provider implementation bytes differ from frozen manifest"
        )

    argv = manifest.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(x, str) and x.strip() for x in argv)
    ):
        raise FrozenObservationRuntimeError("observation provider argv malformed")
    if implementation_rel not in argv:
        raise FrozenObservationRuntimeError(
            "observation provider argv lost implementation identity"
        )
    try:
        timeout = float(manifest.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise FrozenObservationRuntimeError("observation provider timeout malformed") from exc
    if timeout <= 0:
        raise FrozenObservationRuntimeError("observation provider timeout must be > 0")

    raw_fields = manifest.get("output_fields")
    if not isinstance(raw_fields, list):
        raise FrozenObservationRuntimeError("observation provider output_fields missing")
    fields = tuple(str(x).strip() for x in raw_fields)
    if not fields or list(fields) != sorted(set(fields)):
        raise FrozenObservationRuntimeError(
            "observation provider output_fields must be sorted and unique"
        )

    family = str(family_id).strip()
    task = str(task_id).strip()
    if not family or not task:
        raise FrozenObservationRuntimeError("family_id and task_id required")
    request = {
        "schema": OBSERVATION_PROVIDER_REQUEST_SCHEMA,
        "family_id": family,
        "task_id": task,
        "budget_remaining": budget_remaining,
        "step_index": step_index,
    }
    raw_request = canonical_json_bytes(request) + b"\n"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "PYTHONHASHSEED": "0",
        "DGC_MATERIALIZATION_ROOT": str(materialization),
    }
    try:
        proc = subprocess.run(
            [*NETWORK_ISOLATOR, *argv],
            cwd=root,
            env=env,
            input=raw_request,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FrozenObservationRuntimeError("observation provider timed out") from exc
    except OSError as exc:
        raise FrozenObservationRuntimeError(
            "observation provider could not start with network isolation"
        ) from exc

    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise FrozenObservationRuntimeError(
            f"observation provider exited nonzero: {proc.returncode}"
        )
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenObservationRuntimeError(
            "observation provider stdout is not one JSON response"
        ) from exc
    if (
        not isinstance(response, dict)
        or response.get("schema") != OBSERVATION_PROVIDER_RESPONSE_SCHEMA
    ):
        raise FrozenObservationRuntimeError("observation provider response schema mismatch")
    if response.get("family_id") != family or response.get("task_id") != task:
        raise FrozenObservationRuntimeError(
            "observation provider response identity mismatch"
        )
    if response.get("confirmatory_label_access") is not False:
        raise FrozenObservationRuntimeError(
            "observation provider response illegally claims label access"
        )
    if response.get("post_outcome_access") is not False:
        raise FrozenObservationRuntimeError(
            "observation provider response illegally claims post-outcome access"
        )

    observations = response.get("observations")
    if not isinstance(observations, Mapping):
        raise FrozenObservationRuntimeError("observation provider observations missing")
    observed = {str(k): v for k, v in observations.items()}
    if tuple(sorted(observed)) != fields:
        raise FrozenObservationRuntimeError(
            "observation provider response fields differ from frozen manifest"
        )
    response_fields = response.get("output_fields")
    if not isinstance(response_fields, list) or tuple(response_fields) != fields:
        raise FrozenObservationRuntimeError(
            "observation provider output_fields response mismatch"
        )
    source_digest = _sha(
        "observation source_manifest_digest", response.get("source_manifest_digest")
    )

    return FrozenObservationResult(
        observations=observed,
        output_fields=fields,
        source_manifest_digest=source_digest,
        request_digest=hashlib.sha256(canonical_json_bytes(request)).hexdigest(),
        response_digest=hashlib.sha256(canonical_json_bytes(response)).hexdigest(),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        component_sha256=component_sha,
        implementation_sha256=implementation_sha,
    )
