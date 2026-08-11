"""Fail-closed execution readiness for REAL-TRANSFER-01.

This module never runs a scientific cohort and never writes a verdict.  It only decides
whether the already-preregistered external experiment has enough frozen, content-bound
inputs to *begin* scientific execution.  Missing or malformed prerequisites map to
NOT_TESTED, not to scientific failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.real_transfer_01.contract import ContractError
from experiments.real_transfer_01.evaluator import REQUIRED_POLICIES
from experiments.real_transfer_01.preflight import (
    authority_from_contamination,
    digest_file,
    validate_calibration_binding,
    validate_comparators,
    validate_model_manifest,
    validate_source_manifest,
)
from experiments.real_transfer_01.semantic_gate import self_test as semantic_self_test
from experiments.real_transfer_01.temporal_gate import analyze as temporal_analyze

EXPERIMENT_DIR = ROOT / "experiments" / "real_transfer_01"
DEFAULT_SOURCE_MANIFEST = EXPERIMENT_DIR / "SOURCE_MANIFEST.json"
DEFAULT_MODEL_MANIFEST = EXPERIMENT_DIR / "MODEL_MANIFEST.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"path escapes repository root: {path}") from exc


def committed_clean(path: Path, *, root: Path = ROOT) -> bool:
    rel = _relative_to_root(path, root)
    if _git("cat-file", "-e", f"HEAD:{rel}", root=root).returncode != 0:
        return False
    return _git("diff", "--quiet", "HEAD", "--", rel, root=root).returncode == 0


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ContractError(f"JSON root must be object: {path}")
    return payload


def _require_hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ContractError(f"{field} must be lowercase 64-hex SHA-256")
    return value


def validate_runtime_binding(manifest: Mapping[str, Any], *, root: Path = ROOT) -> None:
    """Validate model identity plus runnable comparator/calibration binding."""
    validate_model_manifest(manifest)

    policies = manifest.get("policies")
    if not isinstance(policies, list):
        raise ContractError("model manifest policies must be a list")
    validate_comparators(tuple(map(str, policies)))

    implementations = manifest.get("policy_implementations")
    if not isinstance(implementations, Mapping) or set(implementations) != set(REQUIRED_POLICIES):
        raise ContractError("policy_implementations must bind exactly every required policy")
    for policy in REQUIRED_POLICIES:
        binding = implementations[policy]
        if not isinstance(binding, Mapping):
            raise ContractError(f"policy_implementations.{policy} must be an object")
        raw_path = binding.get("path")
        expected_sha = _require_hash(binding.get("sha256"), field=f"policy_implementations.{policy}.sha256")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ContractError(f"policy_implementations.{policy}.path must be non-empty string")
        impl_path = (root / raw_path).resolve()
        _relative_to_root(impl_path, root)
        if not impl_path.is_file():
            raise ContractError(f"policy implementation missing for {policy}: {raw_path}")
        if digest_file(impl_path).sha256 != expected_sha:
            raise ContractError(f"policy implementation sha256 drift for {policy}")

    calibration = manifest.get("calibration_binding")
    if not isinstance(calibration, Mapping):
        raise ContractError("model manifest calibration_binding must be an object")
    validate_calibration_binding(calibration)

    runner_path_raw = manifest.get("runner_path")
    runner_sha = _require_hash(manifest.get("runner_sha256"), field="runner_sha256")
    if not isinstance(runner_path_raw, str) or not runner_path_raw.strip():
        raise ContractError("runner_path must be non-empty repository-relative path")
    runner_path = (root / runner_path_raw).resolve()
    _relative_to_root(runner_path, root)
    if not runner_path.is_file():
        raise ContractError(f"runner_path missing: {runner_path_raw}")
    observed = digest_file(runner_path).sha256
    if observed != runner_sha:
        raise ContractError("runner_sha256 does not bind runner_path bytes")


def validate_source_bytes(manifest: Mapping[str, Any], *, root: Path = ROOT) -> None:
    """Re-hash every locally materialized source path declared in SOURCE_MANIFEST."""
    sources = manifest.get("sources", [])
    for i, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ContractError(f"source[{i}] must be object")
        raw_path = source.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ContractError(f"source[{i}].path missing")
        path = (root / raw_path).resolve()
        _relative_to_root(path, root)
        if not path.is_file():
            raise ContractError(f"source snapshot missing: {raw_path}")
        observed = digest_file(path)
        if observed.byte_length != source.get("byte_length"):
            raise ContractError(f"source[{i}] byte_length drift")
        if observed.sha256 != source.get("sha256"):
            raise ContractError(f"source[{i}] sha256 drift")


def _block(blockers: list[str], code: str, detail: str) -> None:
    blockers.append(f"{code}:{detail}")


def analyze(
    *,
    root: Path = ROOT,
    source_manifest_path: Path | None = None,
    model_manifest_path: Path | None = None,
    require_committed: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    source_path = (source_manifest_path or (root / "experiments/real_transfer_01/SOURCE_MANIFEST.json")).resolve()
    model_path = (model_manifest_path or (root / "experiments/real_transfer_01/MODEL_MANIFEST.json")).resolve()
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    temporal = temporal_analyze(root=root)
    checks["temporal_gate"] = temporal.get("verdict")
    if temporal.get("verdict") != "PASS":
        _block(blockers, "TEMPORAL_GATE", str(temporal.get("verdict")))

    mutations = semantic_self_test()
    killed = sum(item.killed for item in mutations)
    checks["semantic_mutations"] = {"killed": killed, "total": len(mutations)}
    if killed != len(mutations):
        _block(blockers, "SEMANTIC_GATE", f"{killed}/{len(mutations)}")

    source_manifest: Mapping[str, Any] | None = None
    if not source_path.is_file():
        _block(blockers, "SOURCE_MANIFEST_MISSING", _relative_to_root(source_path, root))
    else:
        try:
            source_manifest = _load_json(source_path)
            validate_source_manifest(source_manifest)
            validate_source_bytes(source_manifest, root=root)
            checks["source_manifest"] = "VALID_AND_BYTES_BOUND"
            if require_committed and not committed_clean(source_path, root=root):
                _block(blockers, "SOURCE_MANIFEST_NOT_COMMITTED_CLEAN", _relative_to_root(source_path, root))
        except ContractError as exc:
            _block(blockers, "SOURCE_MANIFEST_INVALID", str(exc))

    model_manifest: Mapping[str, Any] | None = None
    if not model_path.is_file():
        _block(blockers, "MODEL_MANIFEST_MISSING", _relative_to_root(model_path, root))
    else:
        try:
            model_manifest = _load_json(model_path)
            validate_runtime_binding(model_manifest, root=root)
            checks["model_manifest"] = "VALID_AND_RUNNER_BOUND"
            if require_committed and not committed_clean(model_path, root=root):
                _block(blockers, "MODEL_MANIFEST_NOT_COMMITTED_CLEAN", _relative_to_root(model_path, root))
        except ContractError as exc:
            _block(blockers, "MODEL_MANIFEST_INVALID", str(exc))

    authority = "TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN"
    if source_manifest is not None and model_manifest is not None:
        collision = source_manifest.get("collision_audit", {})
        authority = authority_from_contamination(
            model_manifest.get("training_corpus_provenance"),
            bool(collision.get("training_collision_audit_complete")),
        )

    ready = not blockers
    return {
        "gate": "REAL_TRANSFER_01_PREEXECUTION_READINESS",
        "execution_status": "READY_FOR_SCIENTIFIC_EXECUTION" if ready else "NOT_TESTED",
        "scientific_verdict": "NOT_TESTED",
        "authority_ceiling_if_behavioral_pass": authority,
        "checks": checks,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "note": "Readiness is an execution prerequisite only and cannot promote scientific authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    args = parser.parse_args()
    result = analyze(
        source_manifest_path=args.source_manifest,
        model_manifest_path=args.model_manifest,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"REAL-TRANSFER-01 READINESS: {result['execution_status']} "
            f"blockers={result['blocker_count']} scientific_verdict=NOT_TESTED"
        )
        for blocker in result["blockers"]:
            print(f"  - {blocker}")
    return 0 if result["execution_status"] == "READY_FOR_SCIENTIFIC_EXECUTION" else 3


if __name__ == "__main__":
    raise SystemExit(main())
