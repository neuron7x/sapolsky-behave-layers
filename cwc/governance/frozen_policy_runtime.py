from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.execution_manifest_freeze import (
    POLICY_PROTOCOL,
    POLICY_REQUEST_SCHEMA,
    POLICY_RESPONSE_SCHEMA,
    POLICY_STATE_PROTOCOL,
    policy_action_catalog_digest,
    policy_observation_contract_digest,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file

NETWORK_ISOLATOR = ("unshare", "--net", "--")


class FrozenPolicyRuntimeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenPolicyRuntimeError(f"{name} must be lowercase SHA-256")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FrozenPolicyRuntimeError("policy subject path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise FrozenPolicyRuntimeError(f"policy subject symlink rejected: {rel.as_posix()}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FrozenPolicyRuntimeError("policy subject escapes repository root") from exc
    if not resolved.is_file():
        raise FrozenPolicyRuntimeError(f"policy subject missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenPolicyRuntimeError(f"invalid JSON subject: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise FrozenPolicyRuntimeError(f"unexpected policy schema: {path}")
    return payload


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jsonable_mapping(name: str, value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise FrozenPolicyRuntimeError(f"{name} must be a mapping")
    payload = {str(k): v for k, v in value.items()}
    try:
        canonical_json_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise FrozenPolicyRuntimeError(f"{name} must be canonical-JSON serializable") from exc
    return payload


@dataclass(frozen=True, slots=True)
class FrozenPolicyDecision:
    policy_id: str
    action_id: str
    next_state: dict[str, object]
    request_digest: str
    response_digest: str
    stdout_sha256: str
    stderr_sha256: str
    trace: dict[str, object]
    network_isolation: str = "LINUX_UNSHARE_NET_V1"

    @property
    def document(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "action_id": self.action_id,
            "next_state": self.next_state,
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "trace": self.trace,
            "network_isolation": self.network_isolation,
        }


def invoke_frozen_policy(
    *,
    repository_root: Path,
    frozen_policy: Mapping[str, object],
    task_id: str,
    replicate: int,
    observations: Mapping[str, object],
    state: Mapping[str, object] | None = None,
) -> FrozenPolicyDecision:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise FrozenPolicyRuntimeError("repository root missing")

    policy_id = str(frozen_policy.get("policy_id", "")).strip()
    if not policy_id:
        raise FrozenPolicyRuntimeError("frozen policy id missing")
    manifest_path, manifest_rel = _safe_file(root, frozen_policy.get("path"))
    if sha256_file(manifest_path) != _sha("policy manifest sha256", frozen_policy.get("sha256")):
        raise FrozenPolicyRuntimeError("policy manifest bytes differ from freeze")
    manifest = _json(manifest_path, schema="DGC_GOVERNANCE_POLICY_MANIFEST_V1")
    if manifest.get("policy_id") != policy_id:
        raise FrozenPolicyRuntimeError("policy manifest id mismatch")
    if manifest.get("protocol") != POLICY_PROTOCOL:
        raise FrozenPolicyRuntimeError("policy protocol mismatch")
    if manifest.get("request_schema") != POLICY_REQUEST_SCHEMA:
        raise FrozenPolicyRuntimeError("policy request schema mismatch")
    if manifest.get("response_schema") != POLICY_RESPONSE_SCHEMA:
        raise FrozenPolicyRuntimeError("policy response schema mismatch")
    if manifest.get("state_protocol") != POLICY_STATE_PROTOCOL:
        raise FrozenPolicyRuntimeError("policy state protocol mismatch")
    if manifest.get("network_access_allowed") is not False:
        raise FrozenPolicyRuntimeError("policy network access must be disabled")
    if manifest.get("confirmatory_label_access") is not False:
        raise FrozenPolicyRuntimeError("policy confirmatory-label access must be disabled")
    if manifest_rel != frozen_policy.get("path"):
        raise FrozenPolicyRuntimeError("policy manifest path is non-canonical")

    implementation, implementation_rel = _safe_file(root, manifest.get("implementation_path"))
    config, config_rel = _safe_file(root, manifest.get("config_path"))
    implementation_sha = _sha("policy implementation sha256", manifest.get("implementation_sha256"))
    config_sha = _sha("policy config sha256", manifest.get("config_sha256"))
    if sha256_file(implementation) != implementation_sha:
        raise FrozenPolicyRuntimeError("policy implementation bytes differ from frozen manifest")
    if sha256_file(config) != config_sha:
        raise FrozenPolicyRuntimeError("policy config bytes differ from frozen manifest")
    if frozen_policy.get("implementation_path") != implementation_rel or frozen_policy.get("implementation_sha256") != implementation_sha:
        raise FrozenPolicyRuntimeError("policy implementation lineage differs from execution freeze")
    if frozen_policy.get("config_path") != config_rel or frozen_policy.get("config_sha256") != config_sha:
        raise FrozenPolicyRuntimeError("policy config lineage differs from execution freeze")

    config_doc = _json(config, schema="DGC_GOVERNANCE_POLICY_CONFIG_V1")
    if config_doc.get("policy_id") != policy_id:
        raise FrozenPolicyRuntimeError("policy config id mismatch")
    action_ids = config_doc.get("action_ids")
    observation_fields = config_doc.get("observation_fields")
    action_digest = policy_action_catalog_digest(action_ids)
    observation_digest = policy_observation_contract_digest(observation_fields)
    if action_digest != _sha("policy action catalog digest", manifest.get("action_catalog_digest")):
        raise FrozenPolicyRuntimeError("policy action catalog differs from manifest")
    if observation_digest != _sha("policy observation contract digest", manifest.get("observation_contract_digest")):
        raise FrozenPolicyRuntimeError("policy observation contract differs from manifest")
    if frozen_policy.get("action_catalog_digest") != action_digest:
        raise FrozenPolicyRuntimeError("policy action catalog differs from execution freeze")
    if frozen_policy.get("observation_contract_digest") != observation_digest:
        raise FrozenPolicyRuntimeError("policy observation contract differs from execution freeze")

    obs = _jsonable_mapping("observations", observations)
    expected_fields = list(observation_fields)
    if sorted(obs) != expected_fields:
        raise FrozenPolicyRuntimeError(
            f"policy observations must equal frozen contract; expected={expected_fields}; observed={sorted(obs)}"
        )
    state_doc = _jsonable_mapping("state", state or {})
    task = str(task_id).strip()
    if not task:
        raise FrozenPolicyRuntimeError("task_id required")
    if isinstance(replicate, bool) or int(replicate) < 0:
        raise FrozenPolicyRuntimeError("replicate must be a nonnegative integer")

    request = {
        "schema": POLICY_REQUEST_SCHEMA,
        "policy_id": policy_id,
        "task_id": task,
        "replicate": int(replicate),
        "observations": obs,
        "state": state_doc,
        "action_catalog_digest": action_digest,
        "observation_contract_digest": observation_digest,
    }
    raw_request = canonical_json_bytes(request) + b"\n"

    argv = manifest.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise FrozenPolicyRuntimeError("policy argv malformed")
    if implementation_rel not in argv or config_rel not in argv:
        raise FrozenPolicyRuntimeError("policy argv lost frozen implementation/config identity")
    frozen_argv = frozen_policy.get("argv")
    if not isinstance(frozen_argv, list) or list(argv) != frozen_argv:
        raise FrozenPolicyRuntimeError("policy argv differs from execution freeze")
    try:
        timeout = float(manifest.get("timeout_seconds"))
        frozen_timeout = float(frozen_policy.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise FrozenPolicyRuntimeError("policy timeout malformed") from exc
    if timeout <= 0 or abs(timeout - frozen_timeout) > 1e-12:
        raise FrozenPolicyRuntimeError("policy timeout differs from execution freeze")

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
        raise FrozenPolicyRuntimeError("frozen policy timed out") from exc
    except OSError as exc:
        raise FrozenPolicyRuntimeError("frozen policy could not start with network isolation") from exc
    stdout = bytes(proc.stdout or b"")
    stderr = bytes(proc.stderr or b"")
    if proc.returncode != 0:
        raise FrozenPolicyRuntimeError(f"frozen policy exited nonzero: {proc.returncode}")
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenPolicyRuntimeError("policy stdout is not one JSON response") from exc
    if not isinstance(response, dict) or response.get("schema") != POLICY_RESPONSE_SCHEMA:
        raise FrozenPolicyRuntimeError("policy response schema mismatch")
    if response.get("policy_id") != policy_id:
        raise FrozenPolicyRuntimeError("policy response id mismatch")
    action_id = str(response.get("action_id", "")).strip()
    if action_id not in set(action_ids):
        raise FrozenPolicyRuntimeError("policy selected action outside frozen catalog")
    next_state = _jsonable_mapping("next_state", response.get("next_state", {}))
    trace = _jsonable_mapping("trace", response.get("trace"))
    if not trace:
        raise FrozenPolicyRuntimeError("policy response requires non-empty trace")

    return FrozenPolicyDecision(
        policy_id=policy_id,
        action_id=action_id,
        next_state=next_state,
        request_digest=_digest_bytes(canonical_json_bytes(request)),
        response_digest=_digest_bytes(canonical_json_bytes(response)),
        stdout_sha256=_digest_bytes(stdout),
        stderr_sha256=_digest_bytes(stderr),
        trace=trace,
    )
