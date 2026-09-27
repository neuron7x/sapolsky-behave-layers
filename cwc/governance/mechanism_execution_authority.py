from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_trial_sizing import verify_mechanism_trial_sizing_document
from cwc.governance.task_partition import verify_task_partition_document

SCHEMA = "DGC_MECHANISM_EXECUTION_AUTHORITY_V1"


class MechanismExecutionAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise MechanismExecutionAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _json_repo_subject(
    repository_root: Path,
    value: object,
    *,
    expected_sha256: str,
    expected_schema: str,
) -> dict[str, object]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise MechanismExecutionAuthorityError("repository subject path must be relative")
    current = repository_root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise MechanismExecutionAuthorityError(
                f"repository subject symlink rejected: {rel.as_posix()}"
            )
    path = (repository_root / rel).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise MechanismExecutionAuthorityError("repository subject escapes root") from exc
    if not path.is_file():
        raise MechanismExecutionAuthorityError("repository subject file missing")
    if sha256_file(path) != expected_sha256:
        raise MechanismExecutionAuthorityError("repository subject bytes differ from freeze")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismExecutionAuthorityError("invalid repository subject JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != expected_schema:
        raise MechanismExecutionAuthorityError("unexpected repository subject schema")
    return doc


def _task_digest(task_ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(task_ids))))


@dataclass(frozen=True, slots=True)
class MechanismExecutionAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    harness_freeze_digest: str
    task_partition_receipt_digest: str
    mechanism_plan_digest: str
    mechanism_sizing_receipt_digest: str
    confirmatory_task_digest: str
    confirmatory_task_count: int
    policy_role_bindings: tuple[tuple[str, str], ...]
    required_trials_per_task: int
    max_cost_per_unit_usd: float
    global_budget_usd: float
    distributed_spec: dict[str, object]
    distributed_spec_digest: str
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "mechanism_execution_authorized": True,
            "risk_qualification_authorized": False,
            "product_confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
            "commercial_claim_authorized": False,
        }


def build_mechanism_execution_authority(
    *,
    repository_root: Path,
    execution_manifest_freeze_path: Path,
    harness_freeze_path: Path,
    task_partition_path: Path,
    mechanism_sizing_path: Path,
    mechanism_plan: MechanismStatisticalPlan | None = None,
) -> MechanismExecutionAuthority:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise MechanismExecutionAuthorityError("repository root missing")
    plan = mechanism_plan or MechanismStatisticalPlan()
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    partition = verify_task_partition_document(Path(task_partition_path))
    sizing = verify_mechanism_trial_sizing_document(
        Path(mechanism_sizing_path),
        plan=plan,
    )

    family = str(execution.get("family_id", "")).strip()
    if not family or harness.get("family_id") != family or partition.get("family_id") != family:
        raise MechanismExecutionAuthorityError("execution/harness/partition family mismatch")
    execution_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    harness_digest = _sha("harness freeze_digest", harness.get("harness_freeze_digest"))
    if harness.get("execution_manifest_freeze_digest") != execution_digest:
        raise MechanismExecutionAuthorityError("harness is bound to a different execution freeze")

    if partition.get("statistical_plan_digest") != execution.get("statistical_plan_digest"):
        raise MechanismExecutionAuthorityError(
            "task partition product-plan lineage differs from execution freeze"
        )
    if partition.get("task_manifest_digest") != execution.get("task_manifest_digest"):
        raise MechanismExecutionAuthorityError(
            "task partition full population differs from execution freeze"
        )

    confirmatory_ids = tuple(sorted(str(x) for x in partition.get("confirmatory_task_ids", ())))
    if not confirmatory_ids or len(set(confirmatory_ids)) != len(confirmatory_ids):
        raise MechanismExecutionAuthorityError("confirmatory task population malformed")
    confirmatory_digest = _task_digest(confirmatory_ids)
    if confirmatory_digest != _sha(
        "partition confirmatory_task_digest", partition.get("confirmatory_task_digest")
    ):
        raise MechanismExecutionAuthorityError("confirmatory task digest cannot be replayed")
    if confirmatory_digest != _sha(
        "harness confirmatory_task_manifest_digest",
        harness.get("confirmatory_task_manifest_digest"),
    ):
        raise MechanismExecutionAuthorityError(
            "mechanism execution tasks differ from final frozen harness"
        )
    if int(sizing.get("confirmatory_task_count", -1)) != len(confirmatory_ids):
        raise MechanismExecutionAuthorityError(
            "mechanism sizing confirmatory count differs from frozen task population"
        )

    role_rows = harness.get("policy_role_bindings")
    if not isinstance(role_rows, list) or not all(isinstance(row, Mapping) for row in role_rows):
        raise MechanismExecutionAuthorityError("frozen harness policy-role bindings missing")
    role_map = {
        str(row.get("role", "")).strip(): str(row.get("policy_id", "")).strip()
        for row in role_rows
    }
    required_roles = {kind.value for kind in BaselineKind} | {DGC_ROLE}
    if set(role_map) != required_roles or any(not value for value in role_map.values()):
        raise MechanismExecutionAuthorityError("mechanism policy roles are not exact B0-B3 + DGC")
    if len(set(role_map.values())) != 5:
        raise MechanismExecutionAuthorityError("mechanism policy IDs must be unique")
    frozen_roles = tuple(sorted(role_map.items()))

    component_rows = execution.get("components")
    if not isinstance(component_rows, list):
        raise MechanismExecutionAuthorityError("execution component population missing")
    budget_rows = [
        row for row in component_rows
        if isinstance(row, Mapping) and row.get("component") == "budget"
    ]
    if len(budget_rows) != 1:
        raise MechanismExecutionAuthorityError("exactly one frozen budget component required")
    budget_row = budget_rows[0]
    budget_sha = _sha("budget component sha256", budget_row.get("sha256"))
    budget = _json_repo_subject(
        root,
        budget_row.get("path"),
        expected_sha256=budget_sha,
        expected_schema="DGC_BUDGET_MANIFEST_V1",
    )
    try:
        max_cost = float(budget.get("max_cost_usd"))
    except (TypeError, ValueError) as exc:
        raise MechanismExecutionAuthorityError("frozen max_cost_usd is invalid") from exc
    if not (max_cost > 0):
        raise MechanismExecutionAuthorityError("frozen max_cost_usd must be > 0")

    try:
        repeats = int(sizing.get("required_trials_per_task"))
    except (TypeError, ValueError) as exc:
        raise MechanismExecutionAuthorityError("mechanism repeat count is invalid") from exc
    if not plan.min_trials_per_task <= repeats <= plan.max_trials_per_task:
        raise MechanismExecutionAuthorityError("mechanism repeat count outside frozen plan")

    policy_ids = tuple(sorted(role_map.values()))
    global_budget = max_cost * len(confirmatory_ids) * len(policy_ids) * repeats
    spec = DistributedEvalSpec(
        experiment_id=f"DGC-MECHANISM::{family}",
        task_ids=confirmatory_ids,
        policy_ids=policy_ids,
        replicates=repeats,
        max_attempts_per_unit=1,
        lease_ttl_ticks=4,
        max_cost_per_unit_usd=max_cost,
        global_budget_usd=global_budget,
        harness_digest=_sha("comparison_frame_digest", harness.get("comparison_frame_digest")),
        statistical_plan_digest=plan.digest,
    )
    spec_payload = {
        "experiment_id": spec.experiment_id,
        "task_ids": list(spec.task_ids),
        "policy_ids": list(spec.policy_ids),
        "replicates": spec.replicates,
        "max_attempts_per_unit": spec.max_attempts_per_unit,
        "lease_ttl_ticks": spec.lease_ttl_ticks,
        "max_cost_per_unit_usd": spec.max_cost_per_unit_usd,
        "global_budget_usd": spec.global_budget_usd,
        "harness_digest": spec.harness_digest,
        "statistical_plan_digest": spec.statistical_plan_digest,
    }
    payload = {
        "family_id": family,
        "execution_manifest_freeze_digest": execution_digest,
        "harness_freeze_digest": harness_digest,
        "task_partition_receipt_digest": _sha(
            "task partition receipt_digest", partition.get("receipt_digest")
        ),
        "mechanism_plan_digest": plan.digest,
        "mechanism_sizing_receipt_digest": _sha(
            "mechanism sizing receipt_digest", sizing.get("receipt_digest")
        ),
        "confirmatory_task_digest": confirmatory_digest,
        "confirmatory_task_count": len(confirmatory_ids),
        "policy_role_bindings": frozen_roles,
        "required_trials_per_task": repeats,
        "max_cost_per_unit_usd": max_cost,
        "global_budget_usd": global_budget,
        "distributed_spec": spec_payload,
        "distributed_spec_digest": spec.digest,
    }
    return MechanismExecutionAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_mechanism_execution_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MechanismExecutionAuthorityError("mechanism authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismExecutionAuthorityError("invalid mechanism authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise MechanismExecutionAuthorityError("unexpected mechanism authority schema")
    if (
        doc.get("mechanism_execution_authorized") is not True
        or doc.get("risk_qualification_authorized") is not False
        or doc.get("product_confirmatory_execution_authorized") is not False
        or doc.get("product_promotion_authorized") is not False
        or doc.get("commercial_claim_authorized") is not False
    ):
        raise MechanismExecutionAuthorityError("mechanism authority boundary violated")

    spec_payload = doc.get("distributed_spec")
    if not isinstance(spec_payload, Mapping):
        raise MechanismExecutionAuthorityError("distributed spec missing")
    try:
        spec = DistributedEvalSpec(
            experiment_id=str(spec_payload["experiment_id"]),
            task_ids=tuple(str(x) for x in spec_payload["task_ids"]),
            policy_ids=tuple(str(x) for x in spec_payload["policy_ids"]),
            replicates=int(spec_payload["replicates"]),
            max_attempts_per_unit=int(spec_payload["max_attempts_per_unit"]),
            lease_ttl_ticks=int(spec_payload["lease_ttl_ticks"]),
            max_cost_per_unit_usd=float(spec_payload["max_cost_per_unit_usd"]),
            global_budget_usd=float(spec_payload["global_budget_usd"]),
            harness_digest=str(spec_payload["harness_digest"]),
            statistical_plan_digest=str(spec_payload["statistical_plan_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismExecutionAuthorityError("distributed spec cannot be replayed") from exc
    if spec.digest != _sha(
        "distributed_spec_digest", doc.get("distributed_spec_digest")
    ):
        raise MechanismExecutionAuthorityError("distributed spec digest mismatch")
    if spec.statistical_plan_digest != _sha(
        "mechanism_plan_digest", doc.get("mechanism_plan_digest")
    ):
        raise MechanismExecutionAuthorityError("distributed spec uses wrong mechanism plan")
    if len(spec.task_ids) != int(doc.get("confirmatory_task_count", -1)):
        raise MechanismExecutionAuthorityError("authority task count mismatch")
    if spec.replicates != int(doc.get("required_trials_per_task", -1)):
        raise MechanismExecutionAuthorityError("authority replicate count mismatch")

    role_rows = doc.get("policy_role_bindings")
    if (
        not isinstance(role_rows, list)
        or len(role_rows) != 5
        or not all(isinstance(row, list) and len(row) == 2 for row in role_rows)
    ):
        raise MechanismExecutionAuthorityError("authority policy-role bindings malformed")
    role_map = {str(row[0]): str(row[1]) for row in role_rows}
    required_roles = {kind.value for kind in BaselineKind} | {DGC_ROLE}
    if set(role_map) != required_roles or set(role_map.values()) != set(spec.policy_ids):
        raise MechanismExecutionAuthorityError(
            "authority role mapping differs from distributed policy population"
        )

    payload = {
        key: doc[key]
        for key in (
            "family_id",
            "execution_manifest_freeze_digest",
            "harness_freeze_digest",
            "task_partition_receipt_digest",
            "mechanism_plan_digest",
            "mechanism_sizing_receipt_digest",
            "confirmatory_task_digest",
            "confirmatory_task_count",
            "policy_role_bindings",
            "required_trials_per_task",
            "max_cost_per_unit_usd",
            "global_budget_usd",
            "distributed_spec",
            "distributed_spec_digest",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha(
        "authority_digest", doc.get("authority_digest")
    ):
        raise MechanismExecutionAuthorityError("mechanism authority digest mismatch")
    return doc
