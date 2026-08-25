from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verifier_regression import (
    current_runtime_digest,
    current_test_manifest_digest,
    verify_p19_external_verifier_regression_receipt,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS

SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_PLAN_V3"
PLAN_GENERATION = "PRE_OUTCOME_EXTERNAL_VERIFICATION_PLAN_V3"
CANONICAL_PLAN_PATH = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V3.json"
ENTRYPOINT = VERIFIER_ENTRYPOINT
REQUIRED_IMPLEMENTATION_DEPENDENCIES = VERIFIER_RUNTIME_DEPENDENCIES


class P19ExternalVerificationPlanError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanError(f"{name} must be lowercase SHA-256")
    return text


def _git_oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanError(f"{name} must be lowercase 40-hex Git OID")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if not text or text != text.strip() or text.startswith("/") or ".." in Path(text).parts or "\\" in text:
        raise P19ExternalVerificationPlanError(f"{label} must be canonical repository-relative path")
    return text


def _required_regular_file(root: Path, rel: str, *, label: str) -> Path:
    path = root / rel
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise P19ExternalVerificationPlanError(f"{label} missing/invalid")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19ExternalVerificationPlanError(f"{label} escapes repository") from exc
    return resolved


def _runtime_bindings(root: Path) -> tuple[Path, list[dict[str, object]], str]:
    entry = _required_regular_file(root, ENTRYPOINT, label="external verification entrypoint")
    dependencies: list[dict[str, object]] = []
    for rel in REQUIRED_IMPLEMENTATION_DEPENDENCIES:
        path = _required_regular_file(root, rel, label=f"external verifier dependency {rel}")
        dependencies.append({
            "path": rel,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    dependency_digest = sha256_bytes(canonical_json_bytes(dependencies))
    return entry, dependencies, dependency_digest


def _contracts() -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "method_id": CHECK_METHOD_IDS[check_id],
            "command_template": [
                "python", ENTRYPOINT, "--check-id", check_id,
                "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
            ],
            "implementation_status": "IMPLEMENTED",
        }
        for check_id in sorted(REQUIRED_CHECKS)
    ]


def _build_plan_document(
    *,
    repository_root: Path,
    active: bool,
    regression_receipt_path: Path | None,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    entry, dependencies, dependency_digest = _runtime_bindings(root)

    activation_path: str | None = None
    activation_sha: str | None = None
    activation_digest: str | None = None
    activation_source_commit: str | None = None
    activation_source_tree: str | None = None
    activation_test_digest: str | None = None
    if active:
        if regression_receipt_path is None:
            raise P19ExternalVerificationPlanError("active Plan V3 requires verifier regression receipt")
        source = Path(regression_receipt_path)
        if source.is_absolute():
            resolved = source.resolve()
            try:
                activation_path = resolved.relative_to(root).as_posix()
            except ValueError as exc:
                raise P19ExternalVerificationPlanError("regression receipt escapes repository") from exc
        else:
            activation_path = _safe_rel(source.as_posix(), label="regression receipt")
            resolved = (root / activation_path).resolve()
        try:
            receipt = verify_p19_external_verifier_regression_receipt(resolved, repository_root=root)
        except RuntimeError as exc:
            raise P19ExternalVerificationPlanError("active Plan V3 regression receipt replay failed") from exc
        activation_sha = sha256_file(resolved)
        activation_digest = _sha("regression receipt digest", receipt.get("receipt_digest"))
        activation_source_commit = _git_oid("regression source commit", receipt.get("source_commit"))
        activation_source_tree = _git_oid("regression source tree", receipt.get("source_tree"))
        activation_test_digest = _sha("regression test manifest digest", receipt.get("test_manifest_digest"))
        if receipt.get("runtime_manifest_digest") != current_runtime_digest(root):
            raise P19ExternalVerificationPlanError("regression receipt does not match current verifier runtime")
        if activation_test_digest != current_test_manifest_digest(root):
            raise P19ExternalVerificationPlanError("regression receipt does not match current canonical tests")

    payload = {
        "plan_generation": PLAN_GENERATION,
        "frozen_pre_outcome": True,
        "activation_authorized": active,
        "verifier_entrypoint_path": ENTRYPOINT,
        "verifier_entrypoint_sha256": sha256_file(entry),
        "verifier_dependency_manifest_digest": dependency_digest,
        "verifier_dependencies": dependencies,
        "check_contracts": _contracts(),
        "all_check_implementations_complete": True,
        "activation_regression_receipt_path": activation_path,
        "activation_regression_receipt_sha256": activation_sha,
        "activation_regression_receipt_digest": activation_digest,
        "activation_regression_source_commit": activation_source_commit,
        "activation_regression_source_tree": activation_source_tree,
        "activation_regression_test_manifest_digest": activation_test_digest,
        "product_qualification_authorized": False,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "plan_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def build_inactive_p19_external_verification_plan_document(
    *,
    repository_root: Path,
    implemented_check_ids: Sequence[str],
) -> dict[str, object]:
    """Build canonical Plan V3 in an intentionally inactive state.

    Source-code presence is not activation evidence. The inactive builder has no
    path that can set activation_authorized=true.
    """
    declared = tuple(str(value) for value in implemented_check_ids)
    if len(declared) != len(set(declared)) or set(declared) != REQUIRED_CHECKS:
        raise P19ExternalVerificationPlanError(
            "inactive Plan V3 builder requires exact unique implemented check population"
        )
    return _build_plan_document(
        repository_root=repository_root,
        active=False,
        regression_receipt_path=None,
    )


def build_activated_p19_external_verification_plan_document(
    *,
    repository_root: Path,
    regression_receipt_path: Path,
) -> dict[str, object]:
    """Build active Plan V3 only after canonical regression receipt replay."""
    return _build_plan_document(
        repository_root=repository_root,
        active=True,
        regression_receipt_path=regression_receipt_path,
    )


@dataclass(frozen=True, slots=True)
class P19ExternalVerificationPlan:
    plan_generation: str
    frozen_pre_outcome: bool
    activation_authorized: bool
    verifier_entrypoint_path: str
    verifier_entrypoint_sha256: str
    verifier_dependency_manifest_digest: str
    verifier_dependencies: tuple[dict[str, object], ...]
    check_contracts: tuple[dict[str, object], ...]
    all_check_implementations_complete: bool
    activation_regression_receipt_path: str | None
    activation_regression_receipt_sha256: str | None
    activation_regression_receipt_digest: str | None
    activation_regression_source_commit: str | None
    activation_regression_source_tree: str | None
    activation_regression_test_manifest_digest: str | None
    product_qualification_authorized: bool
    plan_digest: str

    def contract(self, check_id: str) -> Mapping[str, object]:
        matches = [row for row in self.check_contracts if row.get("check_id") == check_id]
        if len(matches) != 1:
            raise P19ExternalVerificationPlanError(f"missing/duplicate verification contract: {check_id}")
        return matches[0]


def _verify_dependencies(root: Path, rows: object) -> tuple[dict[str, object], ...]:
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_IMPLEMENTATION_DEPENDENCIES):
        raise P19ExternalVerificationPlanError("external verifier dependency population incomplete")
    normalized: list[dict[str, object]] = []
    for expected, row in zip(REQUIRED_IMPLEMENTATION_DEPENDENCIES, rows, strict=True):
        if not isinstance(row, Mapping):
            raise P19ExternalVerificationPlanError("external verifier dependency row malformed")
        rel = _safe_rel(row.get("path"), label="verifier dependency")
        if rel != expected:
            raise P19ExternalVerificationPlanError("external verifier dependency path differs from canonical manifest")
        path = _required_regular_file(root, rel, label="external verifier dependency")
        digest = _sha("verifier dependency sha256", row.get("sha256"))
        size = int(row.get("bytes", -1))
        if size <= 0 or path.stat().st_size != size or sha256_file(path) != digest:
            raise P19ExternalVerificationPlanError("external verifier dependency bytes differ from frozen plan")
        normalized.append({"path": rel, "sha256": digest, "bytes": size})
    return tuple(normalized)


def load_p19_external_verification_plan(
    path: Path,
    *,
    repository_root: Path,
    require_active: bool = True,
) -> P19ExternalVerificationPlan:
    root = Path(repository_root).resolve()
    source = Path(path)
    if not source.is_absolute():
        source = root / source
    if source.is_symlink() or not source.is_file():
        raise P19ExternalVerificationPlanError("external verification plan must be a regular non-symlink file")
    try:
        raw = source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerificationPlanError("invalid external verification plan JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerificationPlanError("unexpected external verification plan schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerificationPlanError("external verification plan must use canonical JSON bytes")

    payload_keys = (
        "plan_generation", "frozen_pre_outcome", "activation_authorized",
        "verifier_entrypoint_path", "verifier_entrypoint_sha256",
        "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
        "all_check_implementations_complete", "activation_regression_receipt_path",
        "activation_regression_receipt_sha256", "activation_regression_receipt_digest",
        "activation_regression_source_commit", "activation_regression_source_tree",
        "activation_regression_test_manifest_digest", "product_qualification_authorized",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise P19ExternalVerificationPlanError("external verification plan payload incomplete") from exc
    digest = _sha("plan_digest", doc.get("plan_digest"))
    if sha256_bytes(canonical_json_bytes(payload)) != digest:
        raise P19ExternalVerificationPlanError("external verification plan digest mismatch")
    if doc.get("plan_generation") != PLAN_GENERATION:
        raise P19ExternalVerificationPlanError("external verification plan generation mismatch")
    if doc.get("frozen_pre_outcome") is not True:
        raise P19ExternalVerificationPlanError("external verification plan must be frozen pre-outcome")
    if doc.get("product_qualification_authorized") is not False:
        raise P19ExternalVerificationPlanError("verification plan cannot itself authorize product qualification")

    entry_rel = _safe_rel(doc.get("verifier_entrypoint_path"), label="verifier entrypoint")
    if entry_rel != ENTRYPOINT:
        raise P19ExternalVerificationPlanError("external verification entrypoint differs from canonical path")
    entry = _required_regular_file(root, entry_rel, label="external verification entrypoint")
    entry_sha = _sha("verifier_entrypoint_sha256", doc.get("verifier_entrypoint_sha256"))
    if sha256_file(entry) != entry_sha:
        raise P19ExternalVerificationPlanError("external verification entrypoint bytes differ from frozen plan")

    dependencies = _verify_dependencies(root, doc.get("verifier_dependencies"))
    dependency_digest = _sha("verifier_dependency_manifest_digest", doc.get("verifier_dependency_manifest_digest"))
    if sha256_bytes(canonical_json_bytes(list(dependencies))) != dependency_digest:
        raise P19ExternalVerificationPlanError("external verifier dependency manifest digest mismatch")

    rows = doc.get("check_contracts")
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_CHECKS):
        raise P19ExternalVerificationPlanError("external verification contract population incomplete")
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise P19ExternalVerificationPlanError("external verification contract row malformed")
        check_id = str(row.get("check_id", "")).strip()
        if check_id not in REQUIRED_CHECKS or check_id in seen:
            raise P19ExternalVerificationPlanError("external verification contract check population invalid")
        seen.add(check_id)
        method_id = str(row.get("method_id", "")).strip()
        template = row.get("command_template")
        status = str(row.get("implementation_status", "")).strip()
        expected_template = [
            "python", ENTRYPOINT, "--check-id", check_id,
            "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
        ]
        if method_id != CHECK_METHOD_IDS[check_id]:
            raise P19ExternalVerificationPlanError(f"external verification method identity mismatch: {check_id}")
        if template != expected_template:
            raise P19ExternalVerificationPlanError(f"external verification command template mismatch: {check_id}")
        if status not in {"IMPLEMENTED", "NOT_IMPLEMENTED"}:
            raise P19ExternalVerificationPlanError(f"external verification implementation status invalid: {check_id}")
        normalized.append({
            "check_id": check_id,
            "method_id": method_id,
            "command_template": list(template),
            "implementation_status": status,
        })
    if seen != REQUIRED_CHECKS:
        raise P19ExternalVerificationPlanError("external verification contract set differs from required checks")
    normalized.sort(key=lambda row: str(row["check_id"]))
    if rows != normalized:
        raise P19ExternalVerificationPlanError("external verification contracts must be canonically ordered")

    complete = all(row["implementation_status"] == "IMPLEMENTED" for row in normalized)
    if bool(doc.get("all_check_implementations_complete")) != complete:
        raise P19ExternalVerificationPlanError("external verification implementation-completeness flag mismatch")
    active = doc.get("activation_authorized") is True
    activation_fields = (
        "activation_regression_receipt_path", "activation_regression_receipt_sha256",
        "activation_regression_receipt_digest", "activation_regression_source_commit",
        "activation_regression_source_tree", "activation_regression_test_manifest_digest",
    )
    if active:
        if not complete:
            raise P19ExternalVerificationPlanError("external verification plan cannot activate with incomplete checks")
        receipt_rel = _safe_rel(doc.get("activation_regression_receipt_path"), label="activation regression receipt")
        receipt_path = _required_regular_file(root, receipt_rel, label="activation regression receipt")
        receipt_sha = _sha("activation regression receipt sha256", doc.get("activation_regression_receipt_sha256"))
        if sha256_file(receipt_path) != receipt_sha:
            raise P19ExternalVerificationPlanError("activation regression receipt bytes differ from plan")
        try:
            receipt = verify_p19_external_verifier_regression_receipt(receipt_path, repository_root=root)
        except RuntimeError as exc:
            raise P19ExternalVerificationPlanError("activation regression receipt replay failed") from exc
        if receipt.get("receipt_digest") != _sha(
            "activation regression receipt digest", doc.get("activation_regression_receipt_digest")
        ):
            raise P19ExternalVerificationPlanError("activation regression receipt digest differs from plan")
        if receipt.get("source_commit") != _git_oid(
            "activation regression source commit", doc.get("activation_regression_source_commit")
        ):
            raise P19ExternalVerificationPlanError("activation regression source commit differs from plan")
        if receipt.get("source_tree") != _git_oid(
            "activation regression source tree", doc.get("activation_regression_source_tree")
        ):
            raise P19ExternalVerificationPlanError("activation regression source tree differs from plan")
        if receipt.get("test_manifest_digest") != _sha(
            "activation regression test manifest digest", doc.get("activation_regression_test_manifest_digest")
        ):
            raise P19ExternalVerificationPlanError("activation regression test manifest differs from plan")
        if receipt.get("runtime_manifest_digest") != current_runtime_digest(root):
            raise P19ExternalVerificationPlanError("activation regression runtime no longer matches current verifier")
        if receipt.get("test_manifest_digest") != current_test_manifest_digest(root):
            raise P19ExternalVerificationPlanError("activation regression tests no longer match current suite")
    else:
        if any(doc.get(field) is not None for field in activation_fields):
            raise P19ExternalVerificationPlanError("inactive verification plan cannot carry activation regression evidence")
    if require_active and not active:
        raise P19ExternalVerificationPlanError("external verification plan is not activated")

    return P19ExternalVerificationPlan(
        plan_generation=PLAN_GENERATION,
        frozen_pre_outcome=True,
        activation_authorized=active,
        verifier_entrypoint_path=entry_rel,
        verifier_entrypoint_sha256=entry_sha,
        verifier_dependency_manifest_digest=dependency_digest,
        verifier_dependencies=dependencies,
        check_contracts=tuple(normalized),
        all_check_implementations_complete=complete,
        activation_regression_receipt_path=(
            str(doc.get("activation_regression_receipt_path")) if active else None
        ),
        activation_regression_receipt_sha256=(
            str(doc.get("activation_regression_receipt_sha256")) if active else None
        ),
        activation_regression_receipt_digest=(
            str(doc.get("activation_regression_receipt_digest")) if active else None
        ),
        activation_regression_source_commit=(
            str(doc.get("activation_regression_source_commit")) if active else None
        ),
        activation_regression_source_tree=(
            str(doc.get("activation_regression_source_tree")) if active else None
        ),
        activation_regression_test_manifest_digest=(
            str(doc.get("activation_regression_test_manifest_digest")) if active else None
        ),
        product_qualification_authorized=False,
        plan_digest=digest,
    )


def expected_command_argv(
    plan: P19ExternalVerificationPlan,
    *,
    check_id: str,
    p19_path: str,
    evidence_path: str,
) -> tuple[str, ...]:
    row = plan.contract(check_id)
    if row.get("implementation_status") != "IMPLEMENTED":
        raise P19ExternalVerificationPlanError(f"external verification check not implemented: {check_id}")
    return (
        "python", plan.verifier_entrypoint_path, "--check-id", check_id,
        "--p19", _safe_rel(p19_path, label="P19 path"),
        "--evidence-output", _safe_rel(evidence_path, label="verification evidence path"),
    )


def verify_command_against_plan(
    plan: P19ExternalVerificationPlan,
    *,
    check_id: str,
    command_argv: Sequence[str],
    p19_path: str,
    evidence_path: str,
) -> None:
    expected = expected_command_argv(
        plan,
        check_id=check_id,
        p19_path=p19_path,
        evidence_path=evidence_path,
    )
    if tuple(command_argv) != expected:
        raise P19ExternalVerificationPlanError(f"verification command differs from frozen plan: {check_id}")
