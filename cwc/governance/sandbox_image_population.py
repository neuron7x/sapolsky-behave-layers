from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_SANDBOX_IMAGE_POPULATION_V1"
EXECUTION_MODE = "PREBUILT_IMMUTABLE_OCI"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OCI_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SandboxImagePopulationError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise SandboxImagePopulationError(f"{name} must be lowercase SHA-256")
    return text


def _oci_digest(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _OCI_DIGEST_RE.fullmatch(text) is None:
        raise SandboxImagePopulationError(
            f"{name} must be an immutable sha256 OCI digest"
        )
    return text


def _required(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise SandboxImagePopulationError(f"{name} required")
    return text


def task_population_digest(task_ids: Sequence[str]) -> str:
    normalized = tuple(sorted(str(task_id).strip() for task_id in task_ids))
    if not normalized or any(not task_id for task_id in normalized):
        raise SandboxImagePopulationError("task ids must be non-empty")
    if len(normalized) != len(set(normalized)):
        raise SandboxImagePopulationError("task ids must be unique")
    return sha256_bytes(canonical_json_bytes(normalized))


@dataclass(frozen=True, slots=True)
class SandboxImageBinding:
    task_id: str
    task_source_sha256: str
    build_context_sha256: str
    image_reference: str
    container_image_digest: str
    build_receipt_path: str
    build_receipt_sha256: str
    build_receipt_digest: str

    def __post_init__(self) -> None:
        task_id = _required("task_id", self.task_id)
        if "/" in task_id or "\\" in task_id or task_id in {".", ".."}:
            raise SandboxImagePopulationError("task_id must be a canonical task name")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(
            self, "task_source_sha256", _sha("task_source_sha256", self.task_source_sha256)
        )
        object.__setattr__(
            self, "build_context_sha256", _sha("build_context_sha256", self.build_context_sha256)
        )
        receipt_path = str(self.build_receipt_path).strip()
        if not receipt_path:
            raise SandboxImagePopulationError("build_receipt_path required")
        receipt_rel = Path(receipt_path)
        if receipt_rel.is_absolute() or ".." in receipt_rel.parts:
            raise SandboxImagePopulationError(
                "build_receipt_path must be repository-relative"
            )
        object.__setattr__(self, "build_receipt_path", receipt_rel.as_posix())
        object.__setattr__(
            self, "build_receipt_sha256", _sha("build_receipt_sha256", self.build_receipt_sha256)
        )
        object.__setattr__(
            self, "build_receipt_digest", _sha("build_receipt_digest", self.build_receipt_digest)
        )
        digest = _oci_digest("container_image_digest", self.container_image_digest)
        object.__setattr__(self, "container_image_digest", digest)
        image_reference = _required("image_reference", self.image_reference)
        if "@sha256:" not in image_reference or image_reference.rsplit("@", 1)[-1].lower() != digest:
            raise SandboxImagePopulationError(
                "image_reference must be digest-pinned to container_image_digest"
            )
        if any(ch in image_reference for ch in ("\x00", "\n", "\r", " ")):
            raise SandboxImagePopulationError("image_reference contains forbidden characters")
        object.__setattr__(self, "image_reference", image_reference)


@dataclass(frozen=True, slots=True)
class SandboxImagePopulation:
    family_id: str
    runtime: str
    materialization_reference_digest: str
    task_manifest_sha256: str
    expected_task_count: int
    bindings: tuple[SandboxImageBinding, ...]
    population_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "runtime": self.runtime,
            "execution_mode": EXECUTION_MODE,
            "materialization_reference_digest": self.materialization_reference_digest,
            "task_manifest_sha256": self.task_manifest_sha256,
            "expected_task_count": self.expected_task_count,
            "bindings": [asdict(row) for row in self.bindings],
            "population_digest": self.population_digest,
            "external_execution_performed": False,
            "product_promotion_authorized": False,
        }

    def resolve(self, task_id: str) -> SandboxImageBinding:
        task = str(task_id).strip()
        matches = [row for row in self.bindings if row.task_id == task]
        if len(matches) != 1:
            raise SandboxImagePopulationError(
                f"exactly one sandbox image binding required for task {task!r}"
            )
        return matches[0]


def _payload_for_digest(
    *,
    family_id: str,
    runtime: str,
    materialization_reference_digest: str,
    task_manifest_sha256: str,
    expected_task_count: int,
    bindings: tuple[SandboxImageBinding, ...],
) -> dict[str, object]:
    return {
        "family_id": family_id,
        "runtime": runtime,
        "execution_mode": EXECUTION_MODE,
        "materialization_reference_digest": materialization_reference_digest,
        "task_manifest_sha256": task_manifest_sha256,
        "expected_task_count": expected_task_count,
        "bindings": [asdict(row) for row in bindings],
    }


def freeze_sandbox_image_population(
    *,
    family_id: str,
    runtime: str,
    materialization_reference_digest: str,
    task_manifest_sha256: str,
    expected_task_count: int,
    bindings: Sequence[Mapping[str, object] | SandboxImageBinding],
) -> SandboxImagePopulation:
    family = _required("family_id", family_id)
    runtime_id = _required("runtime", runtime)
    reference_digest = _sha(
        "materialization_reference_digest", materialization_reference_digest
    )
    task_manifest = _sha("task_manifest_sha256", task_manifest_sha256)
    if isinstance(expected_task_count, bool):
        raise SandboxImagePopulationError("expected_task_count must be an integer")
    try:
        expected = int(expected_task_count)
    except (TypeError, ValueError) as exc:
        raise SandboxImagePopulationError("expected_task_count must be an integer") from exc
    if expected <= 0:
        raise SandboxImagePopulationError("expected_task_count must be > 0")
    parsed: list[SandboxImageBinding] = []
    for row in bindings:
        if isinstance(row, SandboxImageBinding):
            parsed.append(row)
        elif isinstance(row, Mapping):
            parsed.append(
                SandboxImageBinding(
                    task_id=str(row.get("task_id", "")),
                    task_source_sha256=str(row.get("task_source_sha256", "")),
                    build_context_sha256=str(row.get("build_context_sha256", "")),
                    image_reference=str(row.get("image_reference", "")),
                    container_image_digest=str(row.get("container_image_digest", "")),
                    build_receipt_sha256=str(row.get("build_receipt_sha256", "")),
                )
            )
        else:
            raise SandboxImagePopulationError("invalid sandbox image binding")
    parsed_tuple = tuple(sorted(parsed, key=lambda row: row.task_id))
    if len(parsed_tuple) != expected:
        raise SandboxImagePopulationError(
            f"sandbox image task count mismatch: expected {expected}, observed {len(parsed_tuple)}"
        )
    task_ids = tuple(row.task_id for row in parsed_tuple)
    if len(task_ids) != len(set(task_ids)):
        raise SandboxImagePopulationError("duplicate sandbox image task_id")
    if task_population_digest(task_ids) != task_manifest:
        raise SandboxImagePopulationError(
            "sandbox image task population differs from materialized task manifest"
        )
    payload = _payload_for_digest(
        family_id=family,
        runtime=runtime_id,
        materialization_reference_digest=reference_digest,
        task_manifest_sha256=task_manifest,
        expected_task_count=expected,
        bindings=parsed_tuple,
    )
    digest = sha256_bytes(canonical_json_bytes(payload))
    return SandboxImagePopulation(
        family_id=family,
        runtime=runtime_id,
        materialization_reference_digest=reference_digest,
        task_manifest_sha256=task_manifest,
        expected_task_count=expected,
        bindings=parsed_tuple,
        population_digest=digest,
    )


def verify_sandbox_image_population_document(
    document: Mapping[str, object],
) -> SandboxImagePopulation:
    if document.get("schema") != SCHEMA:
        raise SandboxImagePopulationError("unexpected sandbox image population schema")
    if document.get("execution_mode") != EXECUTION_MODE:
        raise SandboxImagePopulationError("sandbox image population execution mode mismatch")
    if document.get("external_execution_performed") is not False:
        raise SandboxImagePopulationError(
            "sandbox image population cannot claim external execution"
        )
    if document.get("product_promotion_authorized") is not False:
        raise SandboxImagePopulationError(
            "sandbox image population cannot grant product authority"
        )
    rows = document.get("bindings")
    if not isinstance(rows, list):
        raise SandboxImagePopulationError("sandbox image bindings must be a list")
    population = freeze_sandbox_image_population(
        family_id=str(document.get("family_id", "")),
        runtime=str(document.get("runtime", "")),
        materialization_reference_digest=str(
            document.get("materialization_reference_digest", "")
        ),
        task_manifest_sha256=str(document.get("task_manifest_sha256", "")),
        expected_task_count=document.get("expected_task_count", 0),
        bindings=rows,
    )
    if population.population_digest != _sha(
        "population_digest", document.get("population_digest")
    ):
        raise SandboxImagePopulationError("sandbox image population digest mismatch")
    return population
