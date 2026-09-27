from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import sha256_file
from cwc.governance.sandbox_image_build import (
    SandboxImageBuildError,
    verify_sandbox_image_build_receipt_document,
)
from cwc.governance.sandbox_image_population import (
    EXECUTION_MODE,
    SandboxImagePopulation,
    SandboxImagePopulationError,
    verify_sandbox_image_population_document,
)

SCHEMA = "DGC_ENVIRONMENT_MANIFEST_V2"
FAMILY = "TERMINAL_BENCH_2_1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TerminalSandboxAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise TerminalSandboxAuthorityError(
            f"{name} must be lowercase SHA-256"
        )
    return text


def _safe_repo_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise TerminalSandboxAuthorityError(
            "sandbox authority path must be repository-relative"
        )
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise TerminalSandboxAuthorityError(
                f"sandbox authority symlink path rejected: {rel.as_posix()}"
            )
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise TerminalSandboxAuthorityError(
            "sandbox authority path escapes repository root"
        ) from exc
    if not path.is_file():
        raise TerminalSandboxAuthorityError(
            f"sandbox authority file missing: {rel.as_posix()}"
        )
    return path, rel.as_posix()


def verify_terminal_sandbox_environment(
    *,
    repository_root: Path,
    environment: Mapping[str, object],
) -> SandboxImagePopulation:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise TerminalSandboxAuthorityError(
            "repository root missing"
        )
    if environment.get("schema") != SCHEMA:
        raise TerminalSandboxAuthorityError(
            "Terminal sandbox environment schema mismatch"
        )
    if str(environment.get("family_id", "")).strip() != FAMILY:
        raise TerminalSandboxAuthorityError(
            "Terminal sandbox environment family mismatch"
        )
    runtime = str(environment.get("runtime", "")).strip()
    if not runtime:
        raise TerminalSandboxAuthorityError(
            "Terminal sandbox runtime missing"
        )
    if environment.get("execution_mode") != EXECUTION_MODE:
        raise TerminalSandboxAuthorityError(
            "Terminal sandbox must require immutable prebuilt OCI execution"
        )
    reference_digest = _sha(
        "materialization_reference_digest",
        environment.get("materialization_reference_digest"),
    )
    task_manifest = _sha(
        "task_manifest_sha256",
        environment.get("task_manifest_sha256"),
    )
    population_path, population_rel = _safe_repo_file(
        root,
        environment.get("sandbox_image_population_path"),
    )
    if population_rel != str(
        environment.get("sandbox_image_population_path", "")
    ):
        raise TerminalSandboxAuthorityError(
            "sandbox image population path is non-canonical"
        )
    population_file_sha = _sha(
        "sandbox_image_population_sha256",
        environment.get("sandbox_image_population_sha256"),
    )
    if sha256_file(population_path) != population_file_sha:
        raise TerminalSandboxAuthorityError(
            "sandbox image population bytes differ from environment manifest"
        )
    try:
        population_document = json.loads(
            population_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TerminalSandboxAuthorityError(
            "invalid sandbox image population JSON"
        ) from exc
    if not isinstance(population_document, Mapping):
        raise TerminalSandboxAuthorityError(
            "sandbox image population must be a JSON object"
        )
    try:
        population = verify_sandbox_image_population_document(
            population_document
        )
    except SandboxImagePopulationError as exc:
        raise TerminalSandboxAuthorityError(
            "invalid sandbox image population"
        ) from exc

    if population.family_id != FAMILY:
        raise TerminalSandboxAuthorityError(
            "sandbox image population family mismatch"
        )
    if population.runtime != runtime:
        raise TerminalSandboxAuthorityError(
            "sandbox image population runtime mismatch"
        )
    if (
        population.materialization_reference_digest
        != reference_digest
    ):
        raise TerminalSandboxAuthorityError(
            "sandbox image population materialization reference mismatch"
        )
    if population.task_manifest_sha256 != task_manifest:
        raise TerminalSandboxAuthorityError(
            "sandbox image population task manifest mismatch"
        )
    if population.population_digest != _sha(
        "sandbox_image_population_digest",
        environment.get("sandbox_image_population_digest"),
    ):
        raise TerminalSandboxAuthorityError(
            "sandbox image population semantic digest mismatch"
        )

    for binding in population.bindings:
        receipt_path, receipt_rel = _safe_repo_file(
            root,
            binding.build_receipt_path,
        )
        if receipt_rel != binding.build_receipt_path:
            raise TerminalSandboxAuthorityError(
                "sandbox image build receipt path is non-canonical"
            )
        if sha256_file(receipt_path) != binding.build_receipt_sha256:
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: sandbox build receipt bytes differ"
            )
        try:
            raw = json.loads(
                receipt_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: invalid sandbox build receipt JSON"
            ) from exc
        if not isinstance(raw, Mapping):
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: sandbox build receipt must be an object"
            )
        try:
            receipt = verify_sandbox_image_build_receipt_document(
                raw
            )
        except SandboxImageBuildError as exc:
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: invalid sandbox build receipt"
            ) from exc

        expected = {
            "task_id": binding.task_id,
            "task_source_sha256": binding.task_source_sha256,
            "build_context_sha256": binding.build_context_sha256,
            "image_reference": binding.image_reference,
            "container_image_digest": binding.container_image_digest,
        }
        for field, value in expected.items():
            if getattr(receipt, field) != value:
                raise TerminalSandboxAuthorityError(
                    f"{binding.task_id}: build receipt {field} mismatch"
                )
        if receipt.family_id != FAMILY:
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: build receipt family mismatch"
            )
        if receipt.receipt_digest != binding.build_receipt_digest:
            raise TerminalSandboxAuthorityError(
                f"{binding.task_id}: build receipt semantic digest mismatch"
            )

    return population
