from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_statistical_plan import ProductStatisticalPlan

SCHEMA = "DGC_EXECUTION_MANIFEST_FREEZE_V1"
INPUT_SCHEMA = "DGC_EXECUTION_MANIFEST_FREEZE_INPUT_V1"
REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OCI_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MUTABLE_VERSION_ALIASES = frozenset({"latest", "default", "current", "stable", "production", "prod"})

COMPONENT_SCHEMAS = {
    "model_manifest": "DGC_MODEL_MANIFEST_V1",
    "prompt_policy": "DGC_PROMPT_POLICY_V1",
    "tool_manifest": "DGC_TOOL_MANIFEST_V1",
    "environment": "DGC_ENVIRONMENT_MANIFEST_V1",
    "budget": "DGC_BUDGET_MANIFEST_V1",
    "pricing_snapshot": "DGC_PRICING_SNAPSHOT_V1",
    "scorer": "DGC_SCORER_MANIFEST_V1",
}


class ExecutionManifestError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise ExecutionManifestError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ExecutionManifestError(f"{name} required")
    return text


def _finite_nonnegative(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionManifestError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise ExecutionManifestError(f"{name} must be finite and >= 0")
    return result


def _repo_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise ExecutionManifestError("manifest path must be repository-relative")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExecutionManifestError("manifest path escapes repository root") from exc
    if not path.is_file() or path.is_symlink():
        raise ExecutionManifestError(f"manifest must be a regular file: {rel.as_posix()}")
    return path, rel.as_posix()


def _json_manifest(root: Path, value: object, *, expected_schema: str) -> tuple[dict[str, object], Path, str]:
    path, rel = _repo_file(root, value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionManifestError(f"invalid JSON manifest: {rel}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != expected_schema:
        raise ExecutionManifestError(f"unexpected manifest schema for {rel}; expected {expected_schema}")
    return payload, path, rel


def _validate_model(payload: Mapping[str, object]) -> None:
    models = payload.get("models")
    if not isinstance(models, list) or not models:
        raise ExecutionManifestError("model manifest requires a non-empty models list")
    seen: set[tuple[str, str, str]] = set()
    for row in models:
        if not isinstance(row, Mapping):
            raise ExecutionManifestError("invalid model manifest row")
        provider = _req("model.provider", row.get("provider"))
        model_id = _req("model.model_id", row.get("model_id"))
        version = _req("model.model_version", row.get("model_version"))
        if version.lower() in _MUTABLE_VERSION_ALIASES:
            raise ExecutionManifestError("mutable model version alias is prohibited")
        identity = (provider, model_id, version)
        if identity in seen:
            raise ExecutionManifestError("duplicate model identity")
        seen.add(identity)


def _validate_prompt(payload: Mapping[str, object]) -> None:
    _sha("system_prompt_sha256", payload.get("system_prompt_sha256"))
    _sha("template_sha256", payload.get("template_sha256"))


def _validate_tools(payload: Mapping[str, object]) -> None:
    tools = payload.get("tools")
    if not isinstance(tools, list):
        raise ExecutionManifestError("tool manifest requires tools list")
    seen: set[str] = set()
    for row in tools:
        if not isinstance(row, Mapping):
            raise ExecutionManifestError("invalid tool manifest row")
        name = _req("tool.name", row.get("name"))
        _req("tool.version", row.get("version"))
        _sha("tool.contract_sha256", row.get("contract_sha256"))
        if name in seen:
            raise ExecutionManifestError("duplicate tool name")
        seen.add(name)


def _validate_environment(payload: Mapping[str, object]) -> None:
    digest = _req("container_image_digest", payload.get("container_image_digest")).lower()
    if _OCI_DIGEST_RE.fullmatch(digest) is None:
        raise ExecutionManifestError("environment requires immutable OCI sha256 image digest")
    _req("runtime", payload.get("runtime"))


def _validate_budget(payload: Mapping[str, object]) -> None:
    values = [
        _finite_nonnegative("max_tokens", payload.get("max_tokens")),
        _finite_nonnegative("max_cost_usd", payload.get("max_cost_usd")),
        _finite_nonnegative("max_wall_time_s", payload.get("max_wall_time_s")),
        _finite_nonnegative("max_steps", payload.get("max_steps")),
    ]
    if not any(value > 0 for value in values):
        raise ExecutionManifestError("budget manifest cannot contain only zero limits")


def _validate_pricing(payload: Mapping[str, object]) -> None:
    _req("pricing.captured_at", payload.get("captured_at"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ExecutionManifestError("pricing snapshot requires entries")
    for row in entries:
        if not isinstance(row, Mapping):
            raise ExecutionManifestError("invalid pricing row")
        _req("pricing.provider", row.get("provider"))
        _req("pricing.model_id", row.get("model_id"))
        _req("pricing.currency", row.get("currency"))
        _finite_nonnegative("pricing.input_per_million", row.get("input_per_million"))
        _finite_nonnegative("pricing.output_per_million", row.get("output_per_million"))


def _validate_scorer(payload: Mapping[str, object]) -> None:
    _req("scorer.version", payload.get("version"))
    _sha("scorer.implementation_sha256", payload.get("implementation_sha256"))


_VALIDATORS = {
    "model_manifest": _validate_model,
    "prompt_policy": _validate_prompt,
    "tool_manifest": _validate_tools,
    "environment": _validate_environment,
    "budget": _validate_budget,
    "pricing_snapshot": _validate_pricing,
    "scorer": _validate_scorer,
}


@dataclass(frozen=True, slots=True)
class FrozenComponent:
    component: str
    path: str
    sha256: str
    bytes: int
    schema: str


@dataclass(frozen=True, slots=True)
class FrozenGovernancePolicy:
    policy_id: str
    path: str
    sha256: str
    implementation_sha256: str
    config_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenExecutionManifestSet:
    family_id: str
    repository_commit: str
    repository_tree: str
    materialization_reference_path: str
    materialization_reference_digest: str
    materialized_tree_sha256: str
    task_manifest_digest: str
    statistical_plan_digest: str
    statistical_plan: dict[str, object]
    components: tuple[FrozenComponent, ...]
    governance_policies: tuple[FrozenGovernancePolicy, ...]
    prebaseline_comparison_digest: str
    freeze_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "baseline_panel_bound": False,
            "harness_frozen": False,
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def _load_reference(root: Path, value: object, *, expected_commit: str, expected_tree: str) -> tuple[dict[str, object], str, str]:
    path, rel = _repo_file(root, value)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionManifestError("invalid materialization reference JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != REFERENCE_SCHEMA:
        raise ExecutionManifestError("materialization reference must be V2")
    observed_digest = _sha("reference_digest", doc.get("reference_digest"))
    payload = dict(doc)
    payload.pop("reference_digest", None)
    if sha256_bytes(canonical_json_bytes(payload)) != observed_digest:
        raise ExecutionManifestError("materialization reference digest mismatch")
    if doc.get("repository_commit") != expected_commit or doc.get("repository_tree") != expected_tree:
        raise ExecutionManifestError("materialization reference repository identity mismatch")
    return doc, rel, observed_digest


def _family_binding(reference: Mapping[str, object], family_id: str) -> Mapping[str, object]:
    bindings = reference.get("family_bindings")
    if not isinstance(bindings, list):
        raise ExecutionManifestError("materialization reference family bindings missing")
    matches = [row for row in bindings if isinstance(row, Mapping) and row.get("family_id") == family_id]
    if len(matches) != 1:
        raise ExecutionManifestError("materialization reference must contain exactly one requested family binding")
    return matches[0]


def freeze_execution_manifests(
    *,
    repository_root: Path,
    repository_commit: str,
    repository_tree: str,
    family_id: str,
    materialization_reference_path: Path,
    component_paths: Mapping[str, object],
    governance_policy_paths: Mapping[str, object],
    statistical_plan_payload: Mapping[str, object] | None = None,
) -> FrozenExecutionManifestSet:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ExecutionManifestError("repository root missing")
    family = _req("family_id", family_id)
    reference, reference_rel, reference_digest = _load_reference(
        root,
        materialization_reference_path,
        expected_commit=repository_commit,
        expected_tree=repository_tree,
    )
    binding = _family_binding(reference, family)
    materialized_tree = _sha("materialized_tree_sha256", binding.get("materialized_tree_sha256"))
    task_manifest = _sha("materialized_task_manifest_sha256", binding.get("materialized_task_manifest_sha256"))

    if set(component_paths) != set(COMPONENT_SCHEMAS):
        missing = sorted(set(COMPONENT_SCHEMAS) - set(component_paths))
        extra = sorted(set(component_paths) - set(COMPONENT_SCHEMAS))
        raise ExecutionManifestError(f"execution component set mismatch; missing={missing}; extra={extra}")
    components: list[FrozenComponent] = []
    for component in sorted(COMPONENT_SCHEMAS):
        payload, path, rel = _json_manifest(root, component_paths[component], expected_schema=COMPONENT_SCHEMAS[component])
        _VALIDATORS[component](payload)
        components.append(FrozenComponent(
            component=component,
            path=rel,
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            schema=COMPONENT_SCHEMAS[component],
        ))

    if not isinstance(governance_policy_paths, Mapping) or len(governance_policy_paths) < 2:
        raise ExecutionManifestError("at least two governance policies are required for controlled comparison")
    policies: list[FrozenGovernancePolicy] = []
    for policy_id in sorted(str(key).strip() for key in governance_policy_paths):
        if not policy_id:
            raise ExecutionManifestError("empty governance policy id")
        payload, path, rel = _json_manifest(
            root,
            governance_policy_paths[policy_id],
            expected_schema="DGC_GOVERNANCE_POLICY_MANIFEST_V1",
        )
        if _req("governance policy_id", payload.get("policy_id")) != policy_id:
            raise ExecutionManifestError("governance policy id/path binding mismatch")
        policies.append(FrozenGovernancePolicy(
            policy_id=policy_id,
            path=rel,
            sha256=sha256_file(path),
            implementation_sha256=_sha("governance implementation_sha256", payload.get("implementation_sha256")),
            config_sha256=_sha("governance config_sha256", payload.get("config_sha256")),
        ))

    try:
        plan = ProductStatisticalPlan(**dict(statistical_plan_payload or {}))
    except (TypeError, ValueError) as exc:
        raise ExecutionManifestError("invalid frozen product statistical plan") from exc
    plan_payload = asdict(plan)

    component_digest_map = {row.component: row.sha256 for row in components}
    prebaseline = sha256_bytes(canonical_json_bytes({
        "family_id": family,
        "materialization_reference_digest": reference_digest,
        "materialized_tree_sha256": materialized_tree,
        "task_manifest_digest": task_manifest,
        "statistical_plan_digest": plan.digest,
        "components": component_digest_map,
    }))
    freeze_payload = {
        "family_id": family,
        "repository_commit": repository_commit,
        "repository_tree": repository_tree,
        "materialization_reference_path": reference_rel,
        "materialization_reference_digest": reference_digest,
        "materialized_tree_sha256": materialized_tree,
        "task_manifest_digest": task_manifest,
        "statistical_plan_digest": plan.digest,
        "statistical_plan": plan_payload,
        "components": [asdict(row) for row in components],
        "governance_policies": [asdict(row) for row in policies],
        "prebaseline_comparison_digest": prebaseline,
    }
    freeze_digest = sha256_bytes(canonical_json_bytes(freeze_payload))
    return FrozenExecutionManifestSet(
        family_id=family,
        repository_commit=repository_commit,
        repository_tree=repository_tree,
        materialization_reference_path=reference_rel,
        materialization_reference_digest=reference_digest,
        materialized_tree_sha256=materialized_tree,
        task_manifest_digest=task_manifest,
        statistical_plan_digest=plan.digest,
        statistical_plan=plan_payload,
        components=tuple(components),
        governance_policies=tuple(policies),
        prebaseline_comparison_digest=prebaseline,
        freeze_digest=freeze_digest,
    )


def verify_execution_manifest_freeze_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise ExecutionManifestError("execution manifest freeze must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionManifestError("invalid execution manifest freeze JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ExecutionManifestError("unexpected execution manifest freeze schema")
    if doc.get("baseline_panel_bound") is not False or doc.get("harness_frozen") is not False:
        raise ExecutionManifestError("pre-B2 execution freeze cannot claim a frozen final harness")
    if doc.get("confirmatory_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise ExecutionManifestError("execution freeze illegally grants downstream authority")
    freeze_digest = _sha("freeze_digest", doc.get("freeze_digest"))
    payload = {
        key: doc[key]
        for key in (
            "family_id", "repository_commit", "repository_tree",
            "materialization_reference_path", "materialization_reference_digest",
            "materialized_tree_sha256", "task_manifest_digest",
            "statistical_plan_digest", "statistical_plan", "components",
            "governance_policies", "prebaseline_comparison_digest",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != freeze_digest:
        raise ExecutionManifestError("execution manifest freeze digest mismatch")
    return doc
