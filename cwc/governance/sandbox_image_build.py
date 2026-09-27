from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)

SCHEMA = "DGC_SANDBOX_IMAGE_BUILD_RECEIPT_V1"
FAMILY = "TERMINAL_BENCH_2_1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OCI_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SandboxImageBuildError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise SandboxImageBuildError(f"{name} must be lowercase SHA-256")
    return text


def _oci(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _OCI_DIGEST_RE.fullmatch(text) is None:
        raise SandboxImageBuildError(f"{name} must be sha256 OCI digest")
    return text


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_manifest(root)))


def _image_name(registry_prefix: str, task_id: str) -> str:
    prefix = str(registry_prefix).strip().rstrip("/")
    if (
        not prefix
        or "://" in prefix
        or "@" in prefix
        or any(ch in prefix for ch in ("\x00", "\n", "\r", " "))
    ):
        raise SandboxImageBuildError(
            "registry_prefix must be a Docker image namespace without scheme/tag/digest"
        )
    task = str(task_id).strip()
    if _TASK_ID_RE.fullmatch(task) is None:
        raise SandboxImageBuildError("task_id is not a canonical image-name component")
    return f"{prefix}/{task.lower()}"


def _run(
    argv: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> subprocess.CompletedProcess[bytes]:
    try:
        proc = runner(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise SandboxImageBuildError(f"could not execute {argv[0]}") from exc
    if proc.returncode != 0:
        stderr = bytes(proc.stderr or b"").decode("utf-8", errors="replace")[-4000:]
        raise SandboxImageBuildError(
            f"command failed ({proc.returncode}): {' '.join(argv[:4])}; stderr_tail={stderr!r}"
        )
    return proc


def _capture_text(
    argv: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> str:
    return bytes(_run(argv, runner=runner).stdout or b"").decode(
        "utf-8", errors="strict"
    ).strip()


@dataclass(frozen=True, slots=True)
class SandboxImageBuildReceipt:
    family_id: str
    task_id: str
    platform: str
    task_source_sha256: str
    build_context_sha256: str
    dockerfile_sha256: str
    staging_reference: str
    image_reference: str
    container_image_digest: str
    docker_version: str
    buildx_version: str
    build_command: tuple[str, ...]
    build_metadata_json: str
    registry_manifest_json: str
    receipt_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "build_command": list(self.build_command),
            "image_build_performed": True,
            "registry_manifest_resolved": True,
            "benchmark_execution_performed": False,
            "product_promotion_authorized": False,
        }

    @property
    def payload(self) -> dict[str, object]:
        data = self.document
        data.pop("schema", None)
        data.pop("receipt_digest", None)
        data.pop("image_build_performed", None)
        data.pop("registry_manifest_resolved", None)
        data.pop("benchmark_execution_performed", None)
        data.pop("product_promotion_authorized", None)
        return data


def _receipt_digest(payload: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(payload)))


def verify_sandbox_image_build_receipt_document(
    document: Mapping[str, object],
) -> SandboxImageBuildReceipt:
    if document.get("schema") != SCHEMA:
        raise SandboxImageBuildError("unexpected sandbox image build receipt schema")
    if document.get("image_build_performed") is not True:
        raise SandboxImageBuildError("build receipt must attest an executed image build")
    if document.get("registry_manifest_resolved") is not True:
        raise SandboxImageBuildError("build receipt must attest registry resolution")
    if document.get("benchmark_execution_performed") is not False:
        raise SandboxImageBuildError("image build receipt cannot claim benchmark execution")
    if document.get("product_promotion_authorized") is not False:
        raise SandboxImageBuildError("image build receipt cannot grant product authority")

    task_id = str(document.get("task_id", "")).strip()
    if _TASK_ID_RE.fullmatch(task_id) is None:
        raise SandboxImageBuildError("invalid receipt task_id")
    family_id = str(document.get("family_id", "")).strip()
    if family_id != FAMILY:
        raise SandboxImageBuildError("sandbox build receipt family mismatch")
    platform = str(document.get("platform", "")).strip()
    if platform != "linux/amd64":
        raise SandboxImageBuildError("only frozen linux/amd64 sandbox builds are admitted")

    task_source = _sha("task_source_sha256", document.get("task_source_sha256"))
    context = _sha("build_context_sha256", document.get("build_context_sha256"))
    dockerfile = _sha("dockerfile_sha256", document.get("dockerfile_sha256"))
    digest = _oci("container_image_digest", document.get("container_image_digest"))
    staging = str(document.get("staging_reference", "")).strip()
    image_reference = str(document.get("image_reference", "")).strip()
    if not staging or "@" in staging:
        raise SandboxImageBuildError("staging_reference must be a tag reference")
    if "@sha256:" not in image_reference or image_reference.rsplit("@", 1)[-1].lower() != digest:
        raise SandboxImageBuildError("image_reference must be pinned to container_image_digest")
    if image_reference.split("@", 1)[0] != staging.rsplit(":", 1)[0]:
        raise SandboxImageBuildError("staging and immutable image names differ")

    docker_version = str(document.get("docker_version", "")).strip()
    buildx_version = str(document.get("buildx_version", "")).strip()
    if not docker_version or not buildx_version:
        raise SandboxImageBuildError("docker/buildx version evidence missing")
    command_raw = document.get("build_command")
    if (
        not isinstance(command_raw, list)
        or not command_raw
        or not all(isinstance(item, str) and item for item in command_raw)
    ):
        raise SandboxImageBuildError("build_command must be a non-empty string list")
    command = tuple(command_raw)
    required_flags = {
        "--platform",
        "--provenance=false",
        "--sbom=false",
        "--push",
        "--metadata-file",
        "--tag",
        "--no-cache",
        "--pull",
    }
    if not required_flags.issubset(set(command)):
        raise SandboxImageBuildError("build command does not satisfy frozen builder policy")
    if "linux/amd64" not in command:
        raise SandboxImageBuildError("build command platform differs from frozen platform")
    if staging not in command:
        raise SandboxImageBuildError("build command does not target declared staging reference")

    metadata_json = str(document.get("build_metadata_json", ""))
    manifest_json = str(document.get("registry_manifest_json", ""))
    try:
        metadata = json.loads(metadata_json)
        manifest = json.loads(manifest_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SandboxImageBuildError("build metadata/registry manifest JSON invalid") from exc
    if not isinstance(metadata, Mapping) or not isinstance(manifest, Mapping):
        raise SandboxImageBuildError("build metadata/registry manifest must be JSON objects")
    if str(metadata.get("containerimage.digest", "")).strip().lower() != digest:
        raise SandboxImageBuildError("build metadata image digest mismatch")
    if manifest.get("schemaVersion") != 2:
        raise SandboxImageBuildError("registry manifest must be OCI/Docker schemaVersion 2")
    if "mediaType" not in manifest:
        raise SandboxImageBuildError("registry manifest mediaType missing")
    observed_manifest_digest = "sha256:" + hashlib.sha256(
        manifest_json.encode("utf-8")
    ).hexdigest()
    if observed_manifest_digest != digest:
        raise SandboxImageBuildError("registry manifest bytes do not match image digest")

    payload = {
        "family_id": family_id,
        "task_id": task_id,
        "platform": platform,
        "task_source_sha256": task_source,
        "build_context_sha256": context,
        "dockerfile_sha256": dockerfile,
        "staging_reference": staging,
        "image_reference": image_reference,
        "container_image_digest": digest,
        "docker_version": docker_version,
        "buildx_version": buildx_version,
        "build_command": list(command),
        "build_metadata_json": metadata_json,
        "registry_manifest_json": manifest_json,
    }
    receipt_digest = _sha("receipt_digest", document.get("receipt_digest"))
    if _receipt_digest(payload) != receipt_digest:
        raise SandboxImageBuildError("sandbox image build receipt digest mismatch")
    return SandboxImageBuildReceipt(
        family_id=family_id,
        task_id=task_id,
        platform=platform,
        task_source_sha256=task_source,
        build_context_sha256=context,
        dockerfile_sha256=dockerfile,
        staging_reference=staging,
        image_reference=image_reference,
        container_image_digest=digest,
        docker_version=docker_version,
        buildx_version=buildx_version,
        build_command=command,
        build_metadata_json=metadata_json,
        registry_manifest_json=manifest_json,
        receipt_digest=receipt_digest,
    )


def build_and_push_terminal_task_image(
    *,
    task_id: str,
    task_root: Path,
    registry_prefix: str,
    docker_command: str = "docker",
    platform: str = "linux/amd64",
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> SandboxImageBuildReceipt:
    task = str(task_id).strip()
    if _TASK_ID_RE.fullmatch(task) is None:
        raise SandboxImageBuildError("invalid task_id")
    if platform != "linux/amd64":
        raise SandboxImageBuildError("only linux/amd64 is admitted for frozen Terminal-Bench builds")
    root = Path(task_root)
    if root.is_symlink() or not root.is_dir():
        raise SandboxImageBuildError("task_root must be a real directory")
    root = root.resolve()
    environment = root / "environment"
    dockerfile = environment / "Dockerfile"
    if environment.is_symlink() or not environment.is_dir():
        raise SandboxImageBuildError("task environment must be a real directory")
    if dockerfile.is_symlink() or not dockerfile.is_file():
        raise SandboxImageBuildError("task environment Dockerfile must be a regular file")

    task_source = _tree_digest(root)
    context = _tree_digest(environment)
    dockerfile_digest = sha256_file(dockerfile)
    image_name = _image_name(registry_prefix, task)
    staging_reference = f"{image_name}:dgc-{context[:24]}"

    docker_version = _capture_text(
        [docker_command, "version", "--format", "{{json .Client}}"],
        runner=runner,
    )
    buildx_version = _capture_text(
        [docker_command, "buildx", "version"],
        runner=runner,
    )

    with tempfile.TemporaryDirectory(prefix="dgc-buildx-") as temp_dir:
        metadata_path = Path(temp_dir) / "metadata.json"
        command = [
            docker_command,
            "buildx",
            "build",
            "--platform",
            platform,
            "--provenance=false",
            "--sbom=false",
            "--push",
            "--metadata-file",
            str(metadata_path),
            "--tag",
            staging_reference,
            "--no-cache",
            "--pull",
            str(environment),
        ]
        _run(command, runner=runner)
        if metadata_path.is_symlink() or not metadata_path.is_file():
            raise SandboxImageBuildError("buildx metadata file missing")
        metadata_json = metadata_path.read_text(encoding="utf-8")
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise SandboxImageBuildError("buildx metadata is not valid JSON") from exc
    if not isinstance(metadata, Mapping):
        raise SandboxImageBuildError("buildx metadata must be a JSON object")
    digest = _oci("containerimage.digest", metadata.get("containerimage.digest"))
    image_reference = f"{image_name}@{digest}"

    manifest_bytes = bytes(
        _run(
            [docker_command, "buildx", "imagetools", "inspect", "--raw", image_reference],
            runner=runner,
        ).stdout
        or b""
    )
    try:
        manifest_json = manifest_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandboxImageBuildError("registry manifest is not UTF-8 JSON") from exc
    observed_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    if observed_digest != digest:
        raise SandboxImageBuildError(
            "registry-resolved manifest digest differs from buildx metadata"
        )
    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError as exc:
        raise SandboxImageBuildError("registry manifest is not valid JSON") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schemaVersion") != 2:
        raise SandboxImageBuildError("registry manifest must be schemaVersion 2")

    payload = {
        "family_id": FAMILY,
        "task_id": task,
        "platform": platform,
        "task_source_sha256": task_source,
        "build_context_sha256": context,
        "dockerfile_sha256": dockerfile_digest,
        "staging_reference": staging_reference,
        "image_reference": image_reference,
        "container_image_digest": digest,
        "docker_version": docker_version,
        "buildx_version": buildx_version,
        "build_command": command,
        "build_metadata_json": metadata_json,
        "registry_manifest_json": manifest_json,
    }
    receipt = SandboxImageBuildReceipt(
        family_id=FAMILY,
        task_id=task,
        platform=platform,
        task_source_sha256=task_source,
        build_context_sha256=context,
        dockerfile_sha256=dockerfile_digest,
        staging_reference=staging_reference,
        image_reference=image_reference,
        container_image_digest=digest,
        docker_version=docker_version,
        buildx_version=buildx_version,
        build_command=tuple(command),
        build_metadata_json=metadata_json,
        registry_manifest_json=manifest_json,
        receipt_digest=_receipt_digest(payload),
    )
    return verify_sandbox_image_build_receipt_document(receipt.document)
