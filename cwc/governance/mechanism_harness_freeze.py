from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.baseline_panel import (
    BaselineKind,
    BaselinePanelSeal,
    bind_verified_learned_router_fit,
)
from cwc.governance.harness_freeze import BASELINE_INPUT_SCHEMA, DGC_ROLE, _spec_from_row
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.mechanism_b2_fit_authority import verify_mechanism_b2_fit_authority_document
from cwc.governance.mechanism_execution_freeze import (
    COMPONENT_SCHEMAS_MECHANISM,
    verify_mechanism_execution_freeze_document,
)

SCHEMA = "DGC_MECHANISM_HARNESS_FREEZE_V1"


class MechanismHarnessFreezeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise MechanismHarnessFreezeError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MechanismHarnessFreezeError(f"missing regular JSON: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismHarnessFreezeError(f"invalid JSON: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise MechanismHarnessFreezeError(f"unexpected schema for {candidate}")
    return doc


@dataclass(frozen=True, slots=True)
class MechanismPolicyHarness:
    policy_id: str
    governance_policy_digest: str
    harness_full_digest: str


@dataclass(frozen=True, slots=True)
class MechanismPolicyRoleBinding:
    role: str
    policy_id: str


@dataclass(frozen=True, slots=True)
class MechanismHarnessFreeze:
    family_id: str
    execution_manifest_freeze_digest: str
    mechanism_plan_digest: str
    b2_fit_authority_digest: str
    materialized_task_manifest_digest: str
    confirmatory_task_manifest_digest: str
    baseline_panel_input_sha256: str
    baseline_panel_digest: str
    baseline_specs: tuple[dict[str, object], ...]
    comparison_frame_digest: str
    policy_harnesses: tuple[MechanismPolicyHarness, ...]
    policy_role_bindings: tuple[MechanismPolicyRoleBinding, ...]
    harness_freeze_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "execution_manifest_freeze_digest": self.execution_manifest_freeze_digest,
            "mechanism_plan_digest": self.mechanism_plan_digest,
            "b2_fit_authority_digest": self.b2_fit_authority_digest,
            "materialized_task_manifest_digest": self.materialized_task_manifest_digest,
            "confirmatory_task_manifest_digest": self.confirmatory_task_manifest_digest,
            "baseline_panel_input_sha256": self.baseline_panel_input_sha256,
            "baseline_panel_digest": self.baseline_panel_digest,
            "baseline_specs": list(self.baseline_specs),
            "comparison_frame_digest": self.comparison_frame_digest,
            "policy_harnesses": [asdict(row) for row in self.policy_harnesses],
            "policy_role_bindings": [asdict(row) for row in self.policy_role_bindings],
            "harness_freeze_digest": self.harness_freeze_digest,
            "risk_endpoint_bound": False,
            "risk_qualification_authorized": False,
            "harness_frozen": True,
            "mechanism_execution_authorized": False,
            "product_confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def build_mechanism_harness_freeze(
    *,
    execution_manifest_freeze_path: Path,
    mechanism_b2_fit_authority_path: Path,
    baseline_panel_input_path: Path,
) -> MechanismHarnessFreeze:
    execution = verify_mechanism_execution_freeze_document(Path(execution_manifest_freeze_path))
    b2 = verify_mechanism_b2_fit_authority_document(Path(mechanism_b2_fit_authority_path))
    baseline_input = _json(Path(baseline_panel_input_path), BASELINE_INPUT_SCHEMA)
    execution_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    if b2.get("execution_manifest_freeze_digest") != execution_digest:
        raise MechanismHarnessFreezeError("mechanism B2 is bound to a different execution freeze")
    if b2.get("family_id") != execution.get("family_id"):
        raise MechanismHarnessFreezeError("mechanism B2 family differs from execution freeze")

    rows = baseline_input.get("specs")
    if not isinstance(rows, list) or len(rows) != 4 or not all(isinstance(row, Mapping) for row in rows):
        raise MechanismHarnessFreezeError("baseline panel input must contain exactly four specs")
    try:
        specs = [_spec_from_row(row) for row in rows]
    except Exception as exc:
        raise MechanismHarnessFreezeError(str(exc)) from exc
    b2_specs = [row for row in specs if row.kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER]
    if len(b2_specs) != 1:
        raise MechanismHarnessFreezeError("mechanism baseline panel requires exactly one B2 spec")
    prefit = b2_specs[0]
    if prefit.calibration_task_digest or prefit.fitted_model_digest:
        raise MechanismHarnessFreezeError("mechanism baseline input must contain pre-fit B2")
    try:
        fitted_b2 = bind_verified_learned_router_fit(
            prefit,
            feature_schema_digest=str(b2["feature_schema_digest"]),
            training_algorithm_digest=str(b2["training_algorithm_digest"]),
            calibration_task_digest=str(b2["calibration_task_digest"]),
            fitted_model_digest=str(b2["fitted_model_digest"]),
        )
    except ValueError as exc:
        raise MechanismHarnessFreezeError(str(exc)) from exc
    final_specs = tuple(
        fitted_b2 if row.kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER else row
        for row in specs
    )
    panel = BaselinePanelSeal(final_specs)
    if not panel.executable_frozen:
        raise MechanismHarnessFreezeError("mechanism B0-B3 panel is not executable-frozen")

    baseline_ids = baseline_input.get("baseline_policy_ids")
    if not isinstance(baseline_ids, Mapping):
        raise MechanismHarnessFreezeError("baseline_policy_ids mapping required")
    required_kinds = {kind.value for kind in BaselineKind}
    if set(str(key) for key in baseline_ids) != required_kinds:
        raise MechanismHarnessFreezeError("baseline_policy_ids must map exact B0-B3")
    mapped = {str(key): str(value).strip() for key, value in baseline_ids.items()}
    if any(not value for value in mapped.values()) or len(set(mapped.values())) != 4:
        raise MechanismHarnessFreezeError("baseline policy ids must be non-empty and unique")
    dgc_policy_id = str(baseline_input.get("dgc_policy_id", "")).strip()
    if not dgc_policy_id or dgc_policy_id in set(mapped.values()):
        raise MechanismHarnessFreezeError("distinct dgc_policy_id required")
    role_map = {**mapped, DGC_ROLE: dgc_policy_id}
    required_policy_ids = set(role_map.values())

    component_rows = execution.get("components")
    policy_rows = execution.get("governance_policies")
    if not isinstance(component_rows, list) or not isinstance(policy_rows, list):
        raise MechanismHarnessFreezeError("mechanism execution components/policies missing")
    components = {
        str(row["component"]): _sha(f"component {row['component']}", row["sha256"])
        for row in component_rows if isinstance(row, Mapping)
    }
    if set(components) != set(COMPONENT_SCHEMAS_MECHANISM):
        raise MechanismHarnessFreezeError("mechanism execution component population incomplete")
    if "risk_endpoint_manifest" in components:
        raise MechanismHarnessFreezeError("mechanism harness cannot bind risk endpoint")
    governance = {
        str(row["policy_id"]): _sha(f"governance {row['policy_id']}", row["sha256"])
        for row in policy_rows if isinstance(row, Mapping)
    }
    if set(governance) != required_policy_ids:
        raise MechanismHarnessFreezeError("mechanism governance policies must equal B0-B3 + DGC")
    if len(set(governance.values())) != len(governance):
        raise MechanismHarnessFreezeError("governance policy manifests require distinct digests")

    confirmatory_digest = _sha("confirmatory task digest", b2.get("confirmatory_task_digest"))
    materialized_digest = _sha("materialized task digest", execution.get("task_manifest_digest"))
    mechanism_plan_digest = _sha("mechanism plan digest", execution.get("mechanism_plan_digest"))
    common_frame = {
        "family_id": execution["family_id"],
        "components": {key: components[key] for key in sorted(components)},
        "materialized_task_manifest_digest": materialized_digest,
        "confirmatory_task_manifest_digest": confirmatory_digest,
        "mechanism_plan_digest": mechanism_plan_digest,
        "baseline_panel_digest": panel.digest,
        "risk_endpoint_bound": False,
    }
    comparison_frame = sha256_bytes(canonical_json_bytes(common_frame))
    harnesses = tuple(
        MechanismPolicyHarness(
            policy_id=policy_id,
            governance_policy_digest=governance[policy_id],
            harness_full_digest=sha256_bytes(canonical_json_bytes({
                "comparison_frame_digest": comparison_frame,
                "governance_policy_digest": governance[policy_id],
            })),
        )
        for policy_id in sorted(governance)
    )
    role_bindings = tuple(
        MechanismPolicyRoleBinding(role=role, policy_id=role_map[role])
        for role in sorted(role_map)
    )
    serialized_specs = tuple({
        "kind": row.kind.value,
        "implementation_version": row.implementation_version,
        "feature_schema_digest": row.feature_schema_digest,
        "policy_config_digest": row.policy_config_digest,
        "training_algorithm_digest": row.training_algorithm_digest,
        "calibration_task_digest": row.calibration_task_digest,
        "fitted_model_digest": row.fitted_model_digest,
        "digest": row.digest,
    } for row in sorted(final_specs, key=lambda value: value.kind.value))
    payload = {
        "family_id": execution["family_id"],
        "execution_manifest_freeze_digest": execution_digest,
        "mechanism_plan_digest": mechanism_plan_digest,
        "b2_fit_authority_digest": _sha("B2 authority_digest", b2.get("authority_digest")),
        "materialized_task_manifest_digest": materialized_digest,
        "confirmatory_task_manifest_digest": confirmatory_digest,
        "baseline_panel_input_sha256": sha256_file(Path(baseline_panel_input_path)),
        "baseline_panel_digest": panel.digest,
        "baseline_specs": list(serialized_specs),
        "comparison_frame_digest": comparison_frame,
        "policy_harnesses": [asdict(row) for row in harnesses],
        "policy_role_bindings": [asdict(row) for row in role_bindings],
    }
    return MechanismHarnessFreeze(
        family_id=str(execution["family_id"]),
        execution_manifest_freeze_digest=execution_digest,
        mechanism_plan_digest=mechanism_plan_digest,
        b2_fit_authority_digest=_sha("B2 authority_digest", b2.get("authority_digest")),
        materialized_task_manifest_digest=materialized_digest,
        confirmatory_task_manifest_digest=confirmatory_digest,
        baseline_panel_input_sha256=sha256_file(Path(baseline_panel_input_path)),
        baseline_panel_digest=panel.digest,
        baseline_specs=serialized_specs,
        comparison_frame_digest=comparison_frame,
        policy_harnesses=harnesses,
        policy_role_bindings=role_bindings,
        harness_freeze_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_mechanism_harness_freeze_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), SCHEMA)
    if (
        doc.get("risk_endpoint_bound") is not False
        or doc.get("risk_qualification_authorized") is not False
        or doc.get("harness_frozen") is not True
        or doc.get("mechanism_execution_authorized") is not False
        or doc.get("product_confirmatory_execution_authorized") is not False
        or doc.get("product_promotion_authorized") is not False
    ):
        raise MechanismHarnessFreezeError("mechanism harness authority boundary violated")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "mechanism_plan_digest",
            "b2_fit_authority_digest", "materialized_task_manifest_digest",
            "confirmatory_task_manifest_digest", "baseline_panel_input_sha256",
            "baseline_panel_digest", "baseline_specs", "comparison_frame_digest",
            "policy_harnesses", "policy_role_bindings",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha(
        "harness_freeze_digest", doc.get("harness_freeze_digest")
    ):
        raise MechanismHarnessFreezeError("mechanism harness digest mismatch")
    policy_rows = doc.get("policy_harnesses")
    role_rows = doc.get("policy_role_bindings")
    if not isinstance(policy_rows, list) or len(policy_rows) != 5:
        raise MechanismHarnessFreezeError("mechanism harness requires exactly five policy arms")
    if not isinstance(role_rows, list) or len(role_rows) != 5:
        raise MechanismHarnessFreezeError("mechanism harness requires exactly five role bindings")
    return doc
