from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.baseline_panel import BaselineKind, BaselinePanelSeal, BaselinePolicySpec
from cwc.governance.confirmatory_generation import ConfirmatoryGenerationRoot, freeze_confirmatory_generation
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.external_source_authority import (
    ExternalSourceAuthority,
    ExternalSourceStage,
    promote_materialized_verified,
)
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.task_partition import verify_task_partition_document
from cwc.governance.trial_sizing_authority import verify_trial_sizing_authority_document

SCHEMA = "DGC_CONFIRMATORY_ROOT_AUTHORITY_V1"
INPUT_SCHEMA = "DGC_CONFIRMATORY_ROOT_INPUT_V1"
REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
REGISTRY_SCHEMA = "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1"


class ConfirmatoryRootAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ConfirmatoryRootAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise ConfirmatoryRootAuthorityError(f"missing regular JSON file: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfirmatoryRootAuthorityError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise ConfirmatoryRootAuthorityError(f"unexpected schema for {candidate}")
    return doc


def _source_authority(registry_row: Mapping[str, object]) -> ExternalSourceAuthority:
    verification = registry_row.get("verification")
    if not isinstance(verification, Mapping):
        raise ConfirmatoryRootAuthorityError("source verification record missing")
    try:
        authority = ExternalSourceAuthority(
            family_id=str(registry_row["family_id"]),
            stage=ExternalSourceStage.SOURCE_VERIFIED,
            upstream_revision=str(registry_row["upstream_revision"]),
            upstream_identity_digest=str(registry_row["upstream_identity_digest"]),
            source_verification_method=str(verification["verification_method"]),
            source_verification_evidence_digest=str(registry_row["source_verification_evidence_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfirmatoryRootAuthorityError("malformed source authority registry row") from exc
    if authority.digest != _sha("registry authority_digest", registry_row.get("authority_digest")):
        raise ConfirmatoryRootAuthorityError("source authority digest mismatch")
    return authority


def _materialized_authority(
    *, reference: Mapping[str, object], registry: Mapping[str, object], family_id: str
) -> ExternalSourceAuthority:
    family_rows = registry.get("families")
    binding_rows = reference.get("family_bindings")
    if not isinstance(family_rows, list) or not isinstance(binding_rows, list):
        raise ConfirmatoryRootAuthorityError("source/materialization family bindings missing")
    registry_matches = [row for row in family_rows if isinstance(row, Mapping) and row.get("family_id") == family_id]
    binding_matches = [row for row in binding_rows if isinstance(row, Mapping) and row.get("family_id") == family_id]
    if len(registry_matches) != 1 or len(binding_matches) != 1:
        raise ConfirmatoryRootAuthorityError("family authority binding missing or duplicated")
    source = _source_authority(registry_matches[0])
    binding = binding_matches[0]
    if _sha("source_authority_digest", binding.get("source_authority_digest")) != source.digest:
        raise ConfirmatoryRootAuthorityError("materialization binding source authority mismatch")
    materialized = promote_materialized_verified(
        source,
        materialized_tree_sha256=_sha("materialized_tree_sha256", binding.get("materialized_tree_sha256")),
        materialized_task_manifest_sha256=_sha(
            "materialized_task_manifest_sha256", binding.get("materialized_task_manifest_sha256")
        ),
    )
    if materialized.digest != _sha("materialized_authority_digest", binding.get("materialized_authority_digest")):
        raise ConfirmatoryRootAuthorityError("materialized authority digest cannot be reconstructed")
    return materialized


def _baseline_panel(harness: Mapping[str, object]) -> BaselinePanelSeal:
    rows = harness.get("baseline_specs")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ConfirmatoryRootAuthorityError("harness baseline spec population must contain exactly B0-B3")
    specs: list[BaselinePolicySpec] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ConfirmatoryRootAuthorityError("invalid harness baseline spec")
        try:
            spec = BaselinePolicySpec(
                kind=BaselineKind(str(row["kind"])),
                implementation_version=str(row["implementation_version"]),
                feature_schema_digest=str(row["feature_schema_digest"]),
                policy_config_digest=str(row["policy_config_digest"]),
                training_algorithm_digest=row.get("training_algorithm_digest"),
                calibration_task_digest=row.get("calibration_task_digest"),
                fitted_model_digest=row.get("fitted_model_digest"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfirmatoryRootAuthorityError("invalid frozen baseline spec") from exc
        if spec.digest != _sha(f"{spec.kind.value}.digest", row.get("digest")):
            raise ConfirmatoryRootAuthorityError("frozen baseline spec digest mismatch")
        specs.append(spec)
    panel = BaselinePanelSeal(tuple(specs))
    if not panel.executable_frozen or panel.digest != _sha("baseline_panel_digest", harness.get("baseline_panel_digest")):
        raise ConfirmatoryRootAuthorityError("frozen B0-B3 panel cannot be reconstructed")
    return panel


@dataclass(frozen=True, slots=True)
class _SizingAdapter:
    required_trials_per_task: int
    per_claim_alpha: float
    target_power: float


@dataclass(frozen=True, slots=True)
class _HarnessAdapter:
    task_manifest_digest: str
    statistical_plan_digest: str
    baseline_panel_digest: str
    governance_policy_digest: str
    comparison_frame_digest: str
    full_digest: str


@dataclass(frozen=True, slots=True)
class ConfirmatoryRootAuthority:
    family_id: str
    generation_id: str
    execution_manifest_freeze_digest: str
    harness_freeze_digest: str
    trial_sizing_authority_digest: str
    task_partition_receipt_digest: str
    materialized_source_authority_digest: str
    distributed_spec_digest: str
    distributed_spec: dict[str, object]
    root: dict[str, object]
    root_digest: str
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "confirmatory_execution_authorized": True,
            "product_promotion_authorized": False,
        }


def build_confirmatory_root_authority(
    *,
    execution_manifest_freeze_path: Path,
    harness_freeze_path: Path,
    trial_sizing_authority_path: Path,
    task_partition_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
    root_input_path: Path,
) -> ConfirmatoryRootAuthority:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    sizing = verify_trial_sizing_authority_document(Path(trial_sizing_authority_path))
    partition = verify_task_partition_document(Path(task_partition_path))
    reference = _json(Path(materialization_reference_path), REFERENCE_SCHEMA)
    registry = _json(Path(source_registry_path), REGISTRY_SCHEMA)
    root_input = _json(Path(root_input_path), INPUT_SCHEMA)

    family = str(execution.get("family_id", ""))
    execution_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    harness_digest = _sha("harness_freeze_digest", harness.get("harness_freeze_digest"))
    sizing_digest = _sha("trial-sizing authority_digest", sizing.get("authority_digest"))
    partition_digest = _sha("task partition receipt_digest", partition.get("receipt_digest"))
    if any(str(doc.get("family_id", "")) != family for doc in (harness, sizing, partition)):
        raise ConfirmatoryRootAuthorityError("confirmatory root family lineage mismatch")
    if harness.get("execution_manifest_freeze_digest") != execution_digest:
        raise ConfirmatoryRootAuthorityError("harness lineage differs from execution freeze")
    if sizing.get("execution_manifest_freeze_digest") != execution_digest:
        raise ConfirmatoryRootAuthorityError("sizing lineage differs from execution freeze")
    if sizing.get("harness_freeze_digest") != harness_digest:
        raise ConfirmatoryRootAuthorityError("sizing lineage differs from harness freeze")
    if sizing.get("task_partition_receipt_digest") != partition_digest:
        raise ConfirmatoryRootAuthorityError("sizing lineage differs from task partition")

    reference_digest = _sha("materialization reference_digest", reference.get("reference_digest"))
    ref_payload = dict(reference)
    ref_payload.pop("reference_digest", None)
    if sha256_bytes(canonical_json_bytes(ref_payload)) != reference_digest:
        raise ConfirmatoryRootAuthorityError("materialization reference digest mismatch")
    if reference_digest != execution.get("materialization_reference_digest"):
        raise ConfirmatoryRootAuthorityError("root materialization subject differs from execution freeze")
    if _sha("source_registry_sha256", reference.get("source_registry_sha256")) != sha256_file(Path(source_registry_path)):
        raise ConfirmatoryRootAuthorityError("root source registry differs from materialization authority")
    materialized = _materialized_authority(reference=reference, registry=registry, family_id=family)

    panel = _baseline_panel(harness)
    try:
        plan = ProductStatisticalPlan(**dict(execution.get("statistical_plan", {})))
    except (TypeError, ValueError) as exc:
        raise ConfirmatoryRootAuthorityError("frozen product statistical plan cannot be reconstructed") from exc
    if plan.digest != execution.get("statistical_plan_digest") or sizing.get("plan_digest") != plan.digest:
        raise ConfirmatoryRootAuthorityError("statistical plan lineage mismatch")

    confirmatory_tasks = tuple(sorted(str(x) for x in partition.get("confirmatory_task_ids", ())))
    if not confirmatory_tasks:
        raise ConfirmatoryRootAuthorityError("empty confirmatory task population")
    confirmatory_digest = _sha("confirmatory_task_digest", partition.get("confirmatory_task_digest"))
    if confirmatory_digest != harness.get("confirmatory_task_manifest_digest"):
        raise ConfirmatoryRootAuthorityError("harness task identity differs from frozen confirmatory partition")
    if materialized.materialized_task_manifest_sha256 != harness.get("materialized_task_manifest_digest"):
        raise ConfirmatoryRootAuthorityError("harness materialized task identity differs from source authority")

    policy_rows = harness.get("policy_harnesses")
    if not isinstance(policy_rows, list) or len(policy_rows) != 5:
        raise ConfirmatoryRootAuthorityError("confirmatory policy population must contain exact five arms")
    policy_ids = tuple(sorted(str(row.get("policy_id")) for row in policy_rows if isinstance(row, Mapping)))
    if len(policy_ids) != 5 or len(set(policy_ids)) != 5:
        raise ConfirmatoryRootAuthorityError("confirmatory policy population malformed")
    harness_map = {
        str(row["policy_id"]): _HarnessAdapter(
            task_manifest_digest=confirmatory_digest,
            statistical_plan_digest=plan.digest,
            baseline_panel_digest=panel.digest,
            governance_policy_digest=_sha("governance_policy_digest", row.get("governance_policy_digest")),
            comparison_frame_digest=_sha("comparison_frame_digest", harness.get("comparison_frame_digest")),
            full_digest=_sha("harness_full_digest", row.get("harness_full_digest")),
        )
        for row in policy_rows
        if isinstance(row, Mapping)
    }
    sizing_adapter = _SizingAdapter(
        required_trials_per_task=int(sizing["required_trials_per_task"]),
        per_claim_alpha=plan.per_claim_alpha,
        target_power=plan.target_power,
    )

    try:
        generation_id = str(root_input["generation_id"])
        spec = DistributedEvalSpec(
            experiment_id=str(root_input["experiment_id"]),
            task_ids=confirmatory_tasks,
            policy_ids=policy_ids,
            replicates=sizing_adapter.required_trials_per_task,
            max_attempts_per_unit=int(root_input["max_attempts_per_unit"]),
            lease_ttl_ticks=int(root_input["lease_ttl_ticks"]),
            max_cost_per_unit_usd=float(root_input["max_cost_per_unit_usd"]),
            global_budget_usd=float(root_input["global_budget_usd"]),
            harness_digest=str(harness["comparison_frame_digest"]),
            statistical_plan_digest=plan.digest,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfirmatoryRootAuthorityError("invalid distributed confirmatory execution contract") from exc

    try:
        root = freeze_confirmatory_generation(
            generation_id=generation_id,
            repo_commit_oid=str(execution["repository_commit"]),
            repo_tree_oid=str(execution["repository_tree"]),
            source_authority=materialized,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing_adapter,
            policy_harnesses=harness_map,
            distributed_spec=spec,
            confirmatory_task_manifest_sha256=confirmatory_digest,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ConfirmatoryRootAuthorityError("confirmatory generation root freeze failed") from exc
    if root.materialized_task_manifest_sha256 != materialized.materialized_task_manifest_sha256:
        raise ConfirmatoryRootAuthorityError("root lost full materialized workload identity")
    if root.confirmatory_task_manifest_sha256 != confirmatory_digest:
        raise ConfirmatoryRootAuthorityError("root lost held-out confirmatory task identity")

    root_doc = asdict(root)
    spec_doc = asdict(spec)
    payload = {
        "family_id": family,
        "generation_id": generation_id,
        "execution_manifest_freeze_digest": execution_digest,
        "harness_freeze_digest": harness_digest,
        "trial_sizing_authority_digest": sizing_digest,
        "task_partition_receipt_digest": partition_digest,
        "materialized_source_authority_digest": materialized.digest,
        "distributed_spec_digest": spec.digest,
        "distributed_spec": spec_doc,
        "root": root_doc,
        "root_digest": root.root_digest,
    }
    return ConfirmatoryRootAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_confirmatory_root_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), SCHEMA)
    if doc.get("confirmatory_execution_authorized") is not True:
        raise ConfirmatoryRootAuthorityError("confirmatory root must explicitly authorize only the frozen execution population")
    if doc.get("product_promotion_authorized") is not False:
        raise ConfirmatoryRootAuthorityError("confirmatory root cannot authorize product promotion")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "generation_id", "execution_manifest_freeze_digest", "harness_freeze_digest",
            "trial_sizing_authority_digest", "task_partition_receipt_digest",
            "materialized_source_authority_digest", "distributed_spec_digest", "distributed_spec",
            "root", "root_digest",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise ConfirmatoryRootAuthorityError("confirmatory root authority digest mismatch")
    root = doc.get("root")
    spec = doc.get("distributed_spec")
    if not isinstance(root, Mapping) or not isinstance(spec, Mapping):
        raise ConfirmatoryRootAuthorityError("confirmatory root/spec payload missing")
    if root.get("root_digest") != doc.get("root_digest"):
        raise ConfirmatoryRootAuthorityError("nested confirmatory root digest mismatch")
    if root.get("distributed_spec_digest") != doc.get("distributed_spec_digest"):
        raise ConfirmatoryRootAuthorityError("root distributed spec binding mismatch")
    if int(root.get("expected_work_units", 0)) <= 0:
        raise ConfirmatoryRootAuthorityError("empty confirmatory work population")
    tasks = spec.get("task_ids")
    policies = spec.get("policy_ids")
    replicates = int(spec.get("replicates", 0))
    if not isinstance(tasks, list) or not isinstance(policies, list) or not tasks or len(policies) != 5 or replicates <= 0:
        raise ConfirmatoryRootAuthorityError("invalid frozen distributed population")
    if int(root.get("expected_work_units", 0)) != len(tasks) * len(policies) * replicates:
        raise ConfirmatoryRootAuthorityError("confirmatory expected work-unit count mismatch")
    return doc
