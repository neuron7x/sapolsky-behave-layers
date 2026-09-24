from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.task_partition import verify_task_partition_document

SCHEMA = "DGC_GENERALIZATION_REGISTRY_V3"
AXIS_SCHEMA = "DGC_GENERALIZATION_AXIS_MANIFEST_V1"
BASELINE_INPUT_SCHEMA = "DGC_BASELINE_PANEL_INPUT_V1"
GENERALIZATION_FAMILYWISE_ALPHA = 0.05
DGC_ROLE = "DGC"


class GeneralizationRegistryError(RuntimeError):
    pass


class GeneralizationAxis(str, Enum):
    UNSEEN_TASKS = "G1_UNSEEN_TASKS"
    UNSEEN_DOMAIN = "G2_UNSEEN_DOMAIN"
    UNSEEN_MODEL_PROVIDER = "G3_UNSEEN_MODEL_PROVIDER"
    CHANGED_ECONOMICS = "G4_CHANGED_ECONOMICS"
    PERTURBATION_SHIFT = "G5_PERTURBATION_SHIFT"


REQUIRED_AXES = tuple(GeneralizationAxis)
REQUIRED_BASELINE_ROLES = tuple(kind.value for kind in BaselineKind)
REQUIRED_POLICY_ROLES = tuple(sorted((*REQUIRED_BASELINE_ROLES, DGC_ROLE)))


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationRegistryError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise GeneralizationRegistryError(f"{name} required")
    return text


def _finite(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise GeneralizationRegistryError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise GeneralizationRegistryError(f"{name} must be finite")
    return result


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationRegistryError(f"missing regular JSON file: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationRegistryError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise GeneralizationRegistryError(f"unexpected schema for {candidate}")
    return doc


def _repo_file(root: Path, value: Path) -> tuple[Path, str]:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise GeneralizationRegistryError("generalization subject path must be repository-relative")
    candidate = root / rel
    if candidate.is_symlink():
        raise GeneralizationRegistryError("generalization subject symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GeneralizationRegistryError("generalization subject escapes repository root") from exc
    if not resolved.is_file():
        raise GeneralizationRegistryError("generalization subject must be a regular file")
    return resolved, rel.as_posix()


def _component_digest(execution: Mapping[str, object], component: str) -> str:
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise GeneralizationRegistryError("execution component population missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("component") == component]
    if len(matches) != 1:
        raise GeneralizationRegistryError(f"execution component {component!r} missing or duplicated")
    return _sha(f"{component}.sha256", matches[0].get("sha256"))


def _policy_digest_map(execution: Mapping[str, object]) -> dict[str, str]:
    rows = execution.get("governance_policies")
    if not isinstance(rows, list):
        raise GeneralizationRegistryError("execution governance policy population missing")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise GeneralizationRegistryError("malformed governance policy row")
        policy_id = _req("policy_id", row.get("policy_id"))
        if policy_id in result:
            raise GeneralizationRegistryError("duplicate governance policy id")
        result[policy_id] = _sha(f"policy {policy_id}.sha256", row.get("sha256"))
    return result


def _reconstruct_plan(execution: Mapping[str, object]) -> ProductStatisticalPlan:
    payload = execution.get("statistical_plan")
    if not isinstance(payload, Mapping):
        raise GeneralizationRegistryError("frozen statistical plan payload missing")
    try:
        plan = ProductStatisticalPlan(**dict(payload))
    except (TypeError, ValueError) as exc:
        raise GeneralizationRegistryError("frozen statistical plan cannot be reconstructed") from exc
    if plan.digest != _sha("statistical_plan_digest", execution.get("statistical_plan_digest")):
        raise GeneralizationRegistryError("frozen statistical plan digest mismatch")
    return plan


def _baseline_role_map(baseline_input: Mapping[str, object]) -> dict[str, str]:
    raw = baseline_input.get("baseline_policy_ids")
    if not isinstance(raw, Mapping):
        raise GeneralizationRegistryError("baseline panel input lacks baseline_policy_ids")
    required = {kind.value for kind in BaselineKind}
    if set(str(key) for key in raw) != required:
        raise GeneralizationRegistryError("baseline panel input must bind exact B0-B3 roles")
    role_map = {str(key): _req(f"baseline policy {key}", value) for key, value in raw.items()}
    dgc_policy_id = _req("dgc_policy_id", baseline_input.get("dgc_policy_id"))
    if dgc_policy_id in set(role_map.values()):
        raise GeneralizationRegistryError("DGC policy id must be distinct from B0-B3")
    role_map[DGC_ROLE] = dgc_policy_id
    if len(set(role_map.values())) != len(REQUIRED_POLICY_ROLES):
        raise GeneralizationRegistryError("baseline panel semantic role mapping must be unique")
    return role_map


@dataclass(frozen=True, slots=True)
class FrozenGeneralizationAxis:
    axis: str
    manifest_path: str
    manifest_sha256: str
    evaluation_manifest_digest: str
    source_family_id: str
    source_authority_digest: str
    task_population_digest: str
    base_task_population_digest: str
    model_manifest_digest: str
    pricing_snapshot_digest: str
    scorer_digest: str
    perturbation_manifest_digest: str
    reference_baseline_roles: tuple[str, ...]
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    cost_effect_direction: str


@dataclass(frozen=True, slots=True)
class GeneralizationRegistryAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    task_partition_path: str
    task_partition_sha256: str
    task_partition_receipt_digest: str
    baseline_panel_input_path: str
    baseline_panel_input_sha256: str
    primary_confirmatory_task_digest: str
    g1_holdout_task_digest: str
    policy_role_bindings: tuple[tuple[str, str], ...]
    frozen_dgc_policy_digest: str
    generalization_familywise_alpha: float
    per_claim_alpha: float
    axes: tuple[FrozenGeneralizationAxis, ...]
    registry_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "execution_manifest_freeze_digest": self.execution_manifest_freeze_digest,
            "task_partition_path": self.task_partition_path,
            "task_partition_sha256": self.task_partition_sha256,
            "task_partition_receipt_digest": self.task_partition_receipt_digest,
            "baseline_panel_input_path": self.baseline_panel_input_path,
            "baseline_panel_input_sha256": self.baseline_panel_input_sha256,
            "primary_confirmatory_task_digest": self.primary_confirmatory_task_digest,
            "g1_holdout_task_digest": self.g1_holdout_task_digest,
            "policy_role_bindings": [list(row) for row in self.policy_role_bindings],
            "frozen_dgc_policy_digest": self.frozen_dgc_policy_digest,
            "generalization_familywise_alpha": self.generalization_familywise_alpha,
            "per_claim_alpha": self.per_claim_alpha,
            "axes": [asdict(row) for row in self.axes],
            "registry_digest": self.registry_digest,
            "frozen_pre_outcome": True,
            "policy_retuning_allowed": False,
            "generalization_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def _validate_axis_manifest(
    *,
    axis: GeneralizationAxis,
    doc: Mapping[str, object],
    execution: Mapping[str, object],
    partition: Mapping[str, object],
    plan: ProductStatisticalPlan,
) -> dict[str, object]:
    if doc.get("axis") != axis.value:
        raise GeneralizationRegistryError("axis manifest identity mismatch")
    if doc.get("outcomes_observed") is not False or doc.get("policy_retuning_allowed") is not False:
        raise GeneralizationRegistryError("generalization axis must be frozen pre-outcome with no retuning")
    baseline_roles = tuple(str(x) for x in doc.get("reference_baseline_roles", ()))
    if baseline_roles != REQUIRED_BASELINE_ROLES:
        raise GeneralizationRegistryError("each generalization axis must preregister exact B0-B3 comparisons")
    quality_margin = _finite("quality_noninferiority_margin", doc.get("quality_noninferiority_margin"))
    regret_margin = _finite("catastrophic_noninferiority_margin", doc.get("catastrophic_noninferiority_margin"))
    if not math.isclose(quality_margin, plan.quality_noninferiority_margin, rel_tol=0.0, abs_tol=1e-15):
        raise GeneralizationRegistryError("axis quality margin differs from frozen product plan")
    if not math.isclose(regret_margin, plan.catastrophic_regret_noninferiority_margin, rel_tol=0.0, abs_tol=1e-15):
        raise GeneralizationRegistryError("axis catastrophic-regret margin differs from frozen product plan")
    if doc.get("cost_effect_direction") != "BASELINE_MINUS_DGC_POSITIVE":
        raise GeneralizationRegistryError("generalization cost direction must be preregistered as baseline-minus-DGC positive")

    primary_family = str(execution.get("family_id"))
    primary_model = _component_digest(execution, "model_manifest")
    primary_pricing = _component_digest(execution, "pricing_snapshot")
    primary_scorer = _component_digest(execution, "scorer")
    g1_digest = _sha("generalization_task_digest", partition.get("generalization_task_digest"))

    normalized = {
        "evaluation_manifest_digest": _sha("evaluation_manifest_digest", doc.get("evaluation_manifest_digest")),
        "source_family_id": _req("source_family_id", doc.get("source_family_id")),
        "source_authority_digest": _sha("source_authority_digest", doc.get("source_authority_digest")),
        "task_population_digest": _sha("task_population_digest", doc.get("task_population_digest")),
        "base_task_population_digest": _sha("base_task_population_digest", doc.get("base_task_population_digest")),
        "model_manifest_digest": _sha("model_manifest_digest", doc.get("model_manifest_digest")),
        "pricing_snapshot_digest": _sha("pricing_snapshot_digest", doc.get("pricing_snapshot_digest")),
        "scorer_digest": _sha("scorer_digest", doc.get("scorer_digest")),
        "perturbation_manifest_digest": _sha("perturbation_manifest_digest", doc.get("perturbation_manifest_digest")),
        "reference_baseline_roles": baseline_roles,
        "quality_noninferiority_margin": quality_margin,
        "catastrophic_noninferiority_margin": regret_margin,
        "cost_effect_direction": "BASELINE_MINUS_DGC_POSITIVE",
    }

    if normalized["scorer_digest"] != primary_scorer:
        raise GeneralizationRegistryError("G1-G5 must keep scorer fixed; scorer shift requires a new claim generation")
    if axis is GeneralizationAxis.UNSEEN_TASKS:
        if normalized["source_family_id"] != primary_family:
            raise GeneralizationRegistryError("G1 must remain in the primary workload family")
        if normalized["task_population_digest"] != g1_digest:
            raise GeneralizationRegistryError("G1 task population must equal the reserved unseen-task holdout")
        if normalized["model_manifest_digest"] != primary_model or normalized["pricing_snapshot_digest"] != primary_pricing:
            raise GeneralizationRegistryError("G1 must isolate task novelty under primary model/pricing")
    elif axis is GeneralizationAxis.UNSEEN_DOMAIN:
        if normalized["source_family_id"] == primary_family:
            raise GeneralizationRegistryError("G2 requires a distinct preregistered workload domain")
        if normalized["model_manifest_digest"] != primary_model or normalized["pricing_snapshot_digest"] != primary_pricing:
            raise GeneralizationRegistryError("G2 must isolate domain shift under primary model/pricing")
    elif axis is GeneralizationAxis.UNSEEN_MODEL_PROVIDER:
        if normalized["base_task_population_digest"] != g1_digest:
            raise GeneralizationRegistryError("G3 must reuse the reserved G1 task population")
        if normalized["model_manifest_digest"] == primary_model:
            raise GeneralizationRegistryError("G3 requires a distinct frozen model/provider manifest")
        if normalized["pricing_snapshot_digest"] != primary_pricing:
            raise GeneralizationRegistryError("G3 must isolate model/provider shift from economics")
    elif axis is GeneralizationAxis.CHANGED_ECONOMICS:
        if normalized["base_task_population_digest"] != g1_digest:
            raise GeneralizationRegistryError("G4 must reuse the reserved G1 task population")
        if normalized["model_manifest_digest"] != primary_model:
            raise GeneralizationRegistryError("G4 must keep model/provider fixed")
        if normalized["pricing_snapshot_digest"] == primary_pricing:
            raise GeneralizationRegistryError("G4 requires a distinct frozen pricing/economics snapshot")
    elif axis is GeneralizationAxis.PERTURBATION_SHIFT:
        if normalized["base_task_population_digest"] != g1_digest:
            raise GeneralizationRegistryError("G5 perturbations must derive from the reserved G1 task population")
        if normalized["task_population_digest"] == normalized["base_task_population_digest"]:
            raise GeneralizationRegistryError("G5 perturbed population identity must differ from the base task population")
        if normalized["model_manifest_digest"] != primary_model or normalized["pricing_snapshot_digest"] != primary_pricing:
            raise GeneralizationRegistryError("G5 must isolate perturbation shift under primary model/pricing")
    return normalized


def build_generalization_registry(
    *,
    repository_root: Path,
    execution_manifest_freeze_path: Path,
    task_partition_path: Path,
    baseline_panel_input_path: Path,
    axis_manifest_paths: Mapping[GeneralizationAxis, Path],
    policy_role_bindings: Mapping[str, str],
) -> GeneralizationRegistryAuthority:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise GeneralizationRegistryError("repository root missing")
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    partition_file, partition_rel = _repo_file(root, Path(task_partition_path))
    partition = verify_task_partition_document(partition_file)
    baseline_file, baseline_rel = _repo_file(root, Path(baseline_panel_input_path))
    baseline_input = _json(baseline_file, schema=BASELINE_INPUT_SCHEMA)
    if partition.get("family_id") != execution.get("family_id"):
        raise GeneralizationRegistryError("generalization partition/execution family mismatch")
    if partition.get("statistical_plan_digest") != execution.get("statistical_plan_digest"):
        raise GeneralizationRegistryError("generalization partition uses a different statistical plan")
    plan = _reconstruct_plan(execution)

    role_map = {str(role): str(policy_id).strip() for role, policy_id in policy_role_bindings.items()}
    if tuple(sorted(role_map)) != REQUIRED_POLICY_ROLES or len(set(role_map.values())) != len(REQUIRED_POLICY_ROLES):
        raise GeneralizationRegistryError("policy_role_bindings must map exact B0-B3 + DGC to unique policy ids")
    expected_role_map = _baseline_role_map(baseline_input)
    if role_map != expected_role_map:
        raise GeneralizationRegistryError("generalization policy-role mapping differs from baseline panel SSOT")
    policy_digests = _policy_digest_map(execution)
    if set(role_map.values()) != set(policy_digests):
        raise GeneralizationRegistryError("generalization policy roles must equal the frozen five-arm governance population")

    if set(axis_manifest_paths) != set(REQUIRED_AXES):
        raise GeneralizationRegistryError("generalization registry requires exactly G1-G5 manifests")
    axes: list[FrozenGeneralizationAxis] = []
    seen_eval_digests: set[str] = set()
    for axis in REQUIRED_AXES:
        manifest_file, manifest_rel = _repo_file(root, Path(axis_manifest_paths[axis]))
        doc = _json(manifest_file, schema=AXIS_SCHEMA)
        normalized = _validate_axis_manifest(axis=axis, doc=doc, execution=execution, partition=partition, plan=plan)
        evaluation_digest = str(normalized["evaluation_manifest_digest"])
        if evaluation_digest in seen_eval_digests:
            raise GeneralizationRegistryError("G1-G5 evaluation manifests must be independently identified")
        seen_eval_digests.add(evaluation_digest)
        axes.append(FrozenGeneralizationAxis(
            axis=axis.value,
            manifest_path=manifest_rel,
            manifest_sha256=sha256_file(manifest_file),
            **normalized,
        ))

    per_claim_alpha = GENERALIZATION_FAMILYWISE_ALPHA / (
        len(REQUIRED_AXES) * len(REQUIRED_BASELINE_ROLES) * plan.endpoint_count
    )
    payload = {
        "family_id": str(execution["family_id"]),
        "execution_manifest_freeze_digest": _sha("execution freeze_digest", execution.get("freeze_digest")),
        "task_partition_path": partition_rel,
        "task_partition_sha256": sha256_file(partition_file),
        "task_partition_receipt_digest": _sha("partition receipt_digest", partition.get("receipt_digest")),
        "baseline_panel_input_path": baseline_rel,
        "baseline_panel_input_sha256": sha256_file(baseline_file),
        "primary_confirmatory_task_digest": _sha("confirmatory_task_digest", partition.get("confirmatory_task_digest")),
        "g1_holdout_task_digest": _sha("generalization_task_digest", partition.get("generalization_task_digest")),
        "policy_role_bindings": [list(row) for row in sorted(role_map.items())],
        "frozen_dgc_policy_digest": policy_digests[role_map[DGC_ROLE]],
        "generalization_familywise_alpha": GENERALIZATION_FAMILYWISE_ALPHA,
        "per_claim_alpha": per_claim_alpha,
        "axes": [asdict(row) for row in axes],
    }
    return GeneralizationRegistryAuthority(
        family_id=payload["family_id"],
        execution_manifest_freeze_digest=payload["execution_manifest_freeze_digest"],
        task_partition_path=partition_rel,
        task_partition_sha256=payload["task_partition_sha256"],
        task_partition_receipt_digest=payload["task_partition_receipt_digest"],
        baseline_panel_input_path=baseline_rel,
        baseline_panel_input_sha256=payload["baseline_panel_input_sha256"],
        primary_confirmatory_task_digest=payload["primary_confirmatory_task_digest"],
        g1_holdout_task_digest=payload["g1_holdout_task_digest"],
        policy_role_bindings=tuple(sorted(role_map.items())),
        frozen_dgc_policy_digest=payload["frozen_dgc_policy_digest"],
        generalization_familywise_alpha=GENERALIZATION_FAMILYWISE_ALPHA,
        per_claim_alpha=per_claim_alpha,
        axes=tuple(axes),
        registry_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_registry_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=SCHEMA)
    if doc.get("frozen_pre_outcome") is not True or doc.get("policy_retuning_allowed") is not False:
        raise GeneralizationRegistryError("generalization registry must be frozen pre-outcome with no retuning")
    if doc.get("generalization_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise GeneralizationRegistryError("generalization registry cannot grant downstream authority")
    axes = doc.get("axes")
    if not isinstance(axes, list) or len(axes) != len(REQUIRED_AXES):
        raise GeneralizationRegistryError("generalization registry must contain exactly G1-G5")
    observed_axes = tuple(sorted(str(row.get("axis")) for row in axes if isinstance(row, Mapping)))
    if observed_axes != tuple(sorted(axis.value for axis in REQUIRED_AXES)):
        raise GeneralizationRegistryError("generalization axis population mismatch")
    roles = doc.get("policy_role_bindings")
    if (
        not isinstance(roles, list)
        or not all(isinstance(row, list) and len(row) == 2 for row in roles)
        or tuple(sorted(str(row[0]) for row in roles)) != REQUIRED_POLICY_ROLES
    ):
        raise GeneralizationRegistryError("generalization policy role population mismatch")
    for field in ("task_partition_path", "baseline_panel_input_path"):
        rel = Path(str(doc.get(field, "")))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise GeneralizationRegistryError(f"{field} must be repository-relative")
    _sha("task_partition_sha256", doc.get("task_partition_sha256"))
    _sha("baseline_panel_input_sha256", doc.get("baseline_panel_input_sha256"))
    for row in axes:
        if not isinstance(row, Mapping):
            raise GeneralizationRegistryError("malformed generalization axis row")
        manifest_path = Path(str(row.get("manifest_path", "")))
        if manifest_path.is_absolute() or ".." in manifest_path.parts or not manifest_path.parts:
            raise GeneralizationRegistryError("generalization axis manifest path must be repository-relative")
        _sha("axis manifest_sha256", row.get("manifest_sha256"))
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "task_partition_path",
            "task_partition_sha256", "task_partition_receipt_digest",
            "baseline_panel_input_path", "baseline_panel_input_sha256",
            "primary_confirmatory_task_digest", "g1_holdout_task_digest", "policy_role_bindings",
            "frozen_dgc_policy_digest", "generalization_familywise_alpha", "per_claim_alpha", "axes",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("registry_digest", doc.get("registry_digest")):
        raise GeneralizationRegistryError("generalization registry digest mismatch")
    expected_alpha = GENERALIZATION_FAMILYWISE_ALPHA / (
        len(REQUIRED_AXES) * len(REQUIRED_BASELINE_ROLES) * 3
    )
    if not math.isclose(float(doc.get("per_claim_alpha", -1)), expected_alpha, rel_tol=0.0, abs_tol=1e-15):
        raise GeneralizationRegistryError("generalization multiplicity allocation mismatch")
    return doc


def recompute_generalization_registry_from_document(
    *,
    repository_root: Path,
    execution_manifest_freeze_path: Path,
    registry_path: Path,
) -> GeneralizationRegistryAuthority:
    declared = verify_generalization_registry_document(Path(registry_path))
    axes = declared.get("axes")
    assert isinstance(axes, list)
    axis_paths: dict[GeneralizationAxis, Path] = {}
    for row in axes:
        assert isinstance(row, Mapping)
        axis_paths[GeneralizationAxis(str(row["axis"]))] = Path(str(row["manifest_path"]))
    role_rows = declared.get("policy_role_bindings")
    assert isinstance(role_rows, list)
    role_map = {str(row[0]): str(row[1]) for row in role_rows}
    rebuilt = build_generalization_registry(
        repository_root=Path(repository_root),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        task_partition_path=Path(str(declared["task_partition_path"])),
        baseline_panel_input_path=Path(str(declared["baseline_panel_input_path"])),
        axis_manifest_paths=axis_paths,
        policy_role_bindings=role_map,
    )
    if rebuilt.registry_digest != declared.get("registry_digest"):
        raise GeneralizationRegistryError("declared G1-G5 registry differs from subject recomputation")
    return rebuilt
