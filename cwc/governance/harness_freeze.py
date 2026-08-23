from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.b2_fit_authority import verify_b2_fit_authority_document
from cwc.governance.baseline_panel import (
    BaselineKind,
    BaselinePanelSeal,
    BaselinePolicySpec,
    bind_verified_learned_router_fit,
)
from cwc.governance.evaluation_harness import FrozenEvaluationHarness
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_HARNESS_FREEZE_V1"
BASELINE_INPUT_SCHEMA = "DGC_BASELINE_PANEL_INPUT_V1"


class HarnessFreezeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HarnessFreezeError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise HarnessFreezeError(f"missing regular JSON file: {candidate}")
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessFreezeError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise HarnessFreezeError(f"unexpected schema for {candidate}")
    return value


def _spec_from_row(row: Mapping[str, object]) -> BaselinePolicySpec:
    try:
        kind = BaselineKind(str(row["kind"]))
    except (KeyError, ValueError) as exc:
        raise HarnessFreezeError("invalid baseline kind") from exc
    feature = _sha(f"{kind.value}.feature_schema_digest", row.get("feature_schema_digest"))
    config = _sha(f"{kind.value}.policy_config_digest", row.get("policy_config_digest"))
    training = row.get("training_algorithm_digest")
    calibration = row.get("calibration_task_digest")
    fitted = row.get("fitted_model_digest")
    if training is not None:
        training = _sha(f"{kind.value}.training_algorithm_digest", training)
    if calibration is not None:
        calibration = _sha(f"{kind.value}.calibration_task_digest", calibration)
    if fitted is not None:
        fitted = _sha(f"{kind.value}.fitted_model_digest", fitted)
    try:
        return BaselinePolicySpec(
            kind=kind,
            implementation_version=str(row["implementation_version"]),
            feature_schema_digest=feature,
            policy_config_digest=config,
            training_algorithm_digest=training,
            calibration_task_digest=calibration,
            fitted_model_digest=fitted,
        )
    except (KeyError, ValueError) as exc:
        raise HarnessFreezeError(f"invalid baseline spec: {kind.value}") from exc


@dataclass(frozen=True, slots=True)
class FrozenPolicyHarness:
    policy_id: str
    governance_policy_digest: str
    harness_full_digest: str


@dataclass(frozen=True, slots=True)
class HarnessFreezeAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    b2_fit_authority_digest: str
    materialized_task_manifest_digest: str
    confirmatory_task_manifest_digest: str
    baseline_panel_input_sha256: str
    baseline_panel_digest: str
    baseline_specs: tuple[dict[str, object], ...]
    comparison_frame_digest: str
    policy_harnesses: tuple[FrozenPolicyHarness, ...]
    harness_freeze_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "execution_manifest_freeze_digest": self.execution_manifest_freeze_digest,
            "b2_fit_authority_digest": self.b2_fit_authority_digest,
            "materialized_task_manifest_digest": self.materialized_task_manifest_digest,
            "confirmatory_task_manifest_digest": self.confirmatory_task_manifest_digest,
            "baseline_panel_input_sha256": self.baseline_panel_input_sha256,
            "baseline_panel_digest": self.baseline_panel_digest,
            "baseline_specs": list(self.baseline_specs),
            "comparison_frame_digest": self.comparison_frame_digest,
            "policy_harnesses": [asdict(row) for row in self.policy_harnesses],
            "harness_freeze_digest": self.harness_freeze_digest,
            "harness_frozen": True,
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def build_harness_freeze(
    *,
    execution_manifest_freeze_path: Path,
    b2_fit_authority_path: Path,
    baseline_panel_input_path: Path,
) -> HarnessFreezeAuthority:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    b2 = verify_b2_fit_authority_document(Path(b2_fit_authority_path))
    baseline_input = _json(Path(baseline_panel_input_path), schema=BASELINE_INPUT_SCHEMA)

    execution_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    if b2.get("execution_manifest_freeze_digest") != execution_digest:
        raise HarnessFreezeError("B2 authority is bound to a different execution manifest freeze")
    if b2.get("family_id") != execution.get("family_id"):
        raise HarnessFreezeError("B2 authority family differs from execution freeze")
    materialized_task_digest = _sha("materialized task manifest", execution.get("task_manifest_digest"))
    confirmatory_task_digest = _sha("confirmatory task manifest", b2.get("confirmatory_task_digest"))

    rows = baseline_input.get("specs")
    if not isinstance(rows, list) or len(rows) != 4 or not all(isinstance(row, Mapping) for row in rows):
        raise HarnessFreezeError("baseline panel input must contain exactly four specs")
    specs = [_spec_from_row(row) for row in rows]
    b2_specs = [spec for spec in specs if spec.kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER]
    if len(b2_specs) != 1:
        raise HarnessFreezeError("baseline panel requires exactly one B2 spec")
    b2_spec = b2_specs[0]
    if b2_spec.calibration_task_digest or b2_spec.fitted_model_digest:
        raise HarnessFreezeError("baseline panel input must contain pre-fit B2; fit authority binds outcomes")
    if b2_spec.feature_schema_digest != b2.get("feature_schema_digest"):
        raise HarnessFreezeError("B2 baseline feature schema differs from authorized fit")
    if b2_spec.training_algorithm_digest != b2.get("training_algorithm_digest"):
        raise HarnessFreezeError("B2 baseline training algorithm differs from authorized fit")
    fitted_b2 = bind_verified_learned_router_fit(
        b2_spec,
        feature_schema_digest=str(b2["feature_schema_digest"]),
        training_algorithm_digest=str(b2["training_algorithm_digest"]),
        calibration_task_digest=str(b2["calibration_task_digest"]),
        fitted_model_digest=str(b2["fitted_model_digest"]),
    )
    final_specs = tuple(
        fitted_b2 if spec.kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER else spec
        for spec in specs
    )
    panel = BaselinePanelSeal(final_specs)
    if not panel.executable_frozen:
        raise HarnessFreezeError("B0-B3 panel is not executable-frozen")

    baseline_policy_ids = baseline_input.get("baseline_policy_ids")
    if not isinstance(baseline_policy_ids, Mapping):
        raise HarnessFreezeError("baseline_policy_ids mapping required")
    required_kinds = {kind.value for kind in BaselineKind}
    if set(str(key) for key in baseline_policy_ids) != required_kinds:
        raise HarnessFreezeError("baseline_policy_ids must map exactly all B0-B3 kinds")
    mapped_ids = {str(key): str(value).strip() for key, value in baseline_policy_ids.items()}
    if any(not value for value in mapped_ids.values()) or len(set(mapped_ids.values())) != 4:
        raise HarnessFreezeError("baseline policy ids must be non-empty and unique")
    dgc_policy_id = str(baseline_input.get("dgc_policy_id", "")).strip()
    if not dgc_policy_id or dgc_policy_id in set(mapped_ids.values()):
        raise HarnessFreezeError("distinct dgc_policy_id required")
    required_policy_ids = set(mapped_ids.values()) | {dgc_policy_id}

    component_rows = execution.get("components")
    policy_rows = execution.get("governance_policies")
    if not isinstance(component_rows, list) or not isinstance(policy_rows, list):
        raise HarnessFreezeError("execution freeze component/policy rows missing")
    components = {
        str(row["component"]): _sha(f"component {row['component']}", row["sha256"])
        for row in component_rows
        if isinstance(row, Mapping)
    }
    required_components = {
        "model_manifest", "prompt_policy", "tool_manifest", "environment",
        "budget", "pricing_snapshot", "scorer",
    }
    if set(components) != required_components:
        raise HarnessFreezeError("execution freeze component population incomplete")
    governance = {
        str(row["policy_id"]): _sha(f"governance policy {row['policy_id']}", row["sha256"])
        for row in policy_rows
        if isinstance(row, Mapping)
    }
    if set(governance) != required_policy_ids:
        raise HarnessFreezeError("execution governance policies do not equal exact B0-B3 + DGC panel")
    if len(set(governance.values())) != len(governance):
        raise HarnessFreezeError("governance policy manifests must have distinct content digests")

    harnesses: list[FrozenPolicyHarness] = []
    comparison_frames: set[str] = set()
    for policy_id in sorted(governance):
        harness = FrozenEvaluationHarness(
            model_manifest_digest=components["model_manifest"],
            prompt_policy_digest=components["prompt_policy"],
            tool_manifest_digest=components["tool_manifest"],
            task_manifest_digest=confirmatory_task_digest,
            environment_digest=components["environment"],
            budget_digest=components["budget"],
            pricing_snapshot_digest=components["pricing_snapshot"],
            scorer_digest=components["scorer"],
            statistical_plan_digest=_sha("statistical_plan_digest", execution.get("statistical_plan_digest")),
            baseline_panel_digest=panel.digest,
            governance_policy_digest=governance[policy_id],
        )
        comparison_frames.add(harness.comparison_frame_digest)
        harnesses.append(FrozenPolicyHarness(policy_id, governance[policy_id], harness.full_digest))
    if len(comparison_frames) != 1:
        raise HarnessFreezeError("policy harnesses do not share one frozen controlled-comparison frame")
    comparison_frame = next(iter(comparison_frames))

    serialized_specs = tuple({
        "kind": spec.kind.value,
        "implementation_version": spec.implementation_version,
        "feature_schema_digest": spec.feature_schema_digest,
        "policy_config_digest": spec.policy_config_digest,
        "training_algorithm_digest": spec.training_algorithm_digest,
        "calibration_task_digest": spec.calibration_task_digest,
        "fitted_model_digest": spec.fitted_model_digest,
        "digest": spec.digest,
    } for spec in sorted(final_specs, key=lambda value: value.kind.value))
    harness_docs = [asdict(row) for row in harnesses]
    digest_payload = {
        "family_id": execution["family_id"],
        "execution_manifest_freeze_digest": execution_digest,
        "b2_fit_authority_digest": _sha("B2 authority_digest", b2.get("authority_digest")),
        "materialized_task_manifest_digest": materialized_task_digest,
        "confirmatory_task_manifest_digest": confirmatory_task_digest,
        "baseline_panel_input_sha256": sha256_file(Path(baseline_panel_input_path)),
        "baseline_panel_digest": panel.digest,
        "baseline_specs": list(serialized_specs),
        "comparison_frame_digest": comparison_frame,
        "policy_harnesses": harness_docs,
    }
    return HarnessFreezeAuthority(
        family_id=str(execution["family_id"]),
        execution_manifest_freeze_digest=execution_digest,
        b2_fit_authority_digest=_sha("B2 authority_digest", b2.get("authority_digest")),
        materialized_task_manifest_digest=materialized_task_digest,
        confirmatory_task_manifest_digest=confirmatory_task_digest,
        baseline_panel_input_sha256=sha256_file(Path(baseline_panel_input_path)),
        baseline_panel_digest=panel.digest,
        baseline_specs=serialized_specs,
        comparison_frame_digest=comparison_frame,
        policy_harnesses=tuple(harnesses),
        harness_freeze_digest=sha256_bytes(canonical_json_bytes(digest_payload)),
    )


def verify_harness_freeze_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=SCHEMA)
    if doc.get("harness_frozen") is not True:
        raise HarnessFreezeError("harness freeze must explicitly assert harness_frozen=true")
    if doc.get("confirmatory_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise HarnessFreezeError("harness freeze illegally grants downstream authority")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "b2_fit_authority_digest",
            "materialized_task_manifest_digest", "confirmatory_task_manifest_digest",
            "baseline_panel_input_sha256", "baseline_panel_digest", "baseline_specs",
            "comparison_frame_digest", "policy_harnesses",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("harness_freeze_digest", doc.get("harness_freeze_digest")):
        raise HarnessFreezeError("harness freeze digest mismatch")
    materialized = _sha("materialized_task_manifest_digest", doc.get("materialized_task_manifest_digest"))
    confirmatory = _sha("confirmatory_task_manifest_digest", doc.get("confirmatory_task_manifest_digest"))
    if materialized == confirmatory:
        raise HarnessFreezeError("confirmatory task manifest must be distinct from the full materialized workload manifest")
    harnesses = doc.get("policy_harnesses")
    if not isinstance(harnesses, list) or len(harnesses) != 5:
        raise HarnessFreezeError("harness freeze must contain exact five-arm B0-B3 + DGC population")
    rows = [row for row in harnesses if isinstance(row, Mapping)]
    if len(rows) != 5 or len({row.get("policy_id") for row in rows}) != 5:
        raise HarnessFreezeError("harness freeze policy ids must be unique")
    if len({_sha("governance_policy_digest", row.get("governance_policy_digest")) for row in rows}) != 5:
        raise HarnessFreezeError("harness freeze governance digests must be unique")
    for row in rows:
        _sha("harness_full_digest", row.get("harness_full_digest"))
    return doc
