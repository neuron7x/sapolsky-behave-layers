from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.execution_manifest_freeze import (
    COMPONENT_SCHEMAS,
    FrozenComponent,
    _VALIDATORS,
    _family_binding,
    _json_manifest,
    _load_reference,
    _repo_file,
    _sha,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.runtime_cost_contract import RuntimeCostContractError, parse_runtime_cost_contract
from cwc.governance.terminal_sandbox_authority import (
    TerminalSandboxAuthorityError,
    verify_terminal_sandbox_environment,
)

SCHEMA = "DGC_MECHANISM_EXECUTION_FREEZE_V2"
INPUT_SCHEMA = "DGC_MECHANISM_EXECUTION_FREEZE_INPUT_V2"
COMPONENT_SCHEMAS_MECHANISM = {
    key: value for key, value in COMPONENT_SCHEMAS.items()
    if key != "risk_endpoint_manifest"
}


class MechanismExecutionFreezeError(RuntimeError):
    pass


def _translate(exc: Exception) -> MechanismExecutionFreezeError:
    return MechanismExecutionFreezeError(str(exc))


@dataclass(frozen=True, slots=True)
class MechanismExecutionFreeze:
    family_id: str
    repository_commit: str
    repository_tree: str
    materialization_reference_path: str
    materialization_reference_digest: str
    materialized_tree_sha256: str
    task_manifest_digest: str
    statistical_plan_digest: str
    statistical_plan: dict[str, object]
    mechanism_plan_digest: str
    components: tuple[FrozenComponent, ...]
    prebaseline_comparison_digest: str
    freeze_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "risk_endpoint_bound": False,
            "risk_qualification_authorized": False,
            "governance_policies_bound": False,
            "baseline_panel_bound": False,
            "harness_frozen": False,
            "mechanism_execution_authorized": False,
            "product_confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def freeze_mechanism_execution_manifests(
    *,
    repository_root: Path,
    repository_commit: str,
    repository_tree: str,
    family_id: str,
    materialization_reference_path: Path,
    component_paths: Mapping[str, object],
    statistical_plan_payload: Mapping[str, object] | None = None,
    mechanism_plan: MechanismStatisticalPlan | None = None,
) -> MechanismExecutionFreeze:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise MechanismExecutionFreezeError("repository root missing")
    family = str(family_id).strip()
    if not family:
        raise MechanismExecutionFreezeError("family_id required")
    if "risk_endpoint_manifest" in component_paths:
        raise MechanismExecutionFreezeError("mechanism freeze prohibits risk_endpoint_manifest")
    if set(component_paths) != set(COMPONENT_SCHEMAS_MECHANISM):
        missing = sorted(set(COMPONENT_SCHEMAS_MECHANISM) - set(component_paths))
        extra = sorted(set(component_paths) - set(COMPONENT_SCHEMAS_MECHANISM))
        raise MechanismExecutionFreezeError(
            f"mechanism component set mismatch; missing={missing}; extra={extra}"
        )
    try:
        reference, reference_rel, reference_digest = _load_reference(
            root,
            materialization_reference_path,
            expected_commit=repository_commit,
            expected_tree=repository_tree,
        )
        binding = _family_binding(reference, family)
        materialized_tree = _sha("materialized_tree_sha256", binding.get("materialized_tree_sha256"))
        task_manifest = _sha(
            "materialized_task_manifest_sha256",
            binding.get("materialized_task_manifest_sha256"),
        )
    except Exception as exc:
        raise _translate(exc) from exc

    components: list[FrozenComponent] = []
    payloads: dict[str, dict[str, object]] = {}
    try:
        for component in sorted(COMPONENT_SCHEMAS_MECHANISM):
            expected_schema = COMPONENT_SCHEMAS_MECHANISM[component]
            if component == "environment" and family == "TERMINAL_BENCH_2_1":
                expected_schema = "DGC_ENVIRONMENT_MANIFEST_V2"
            payload, path, rel = _json_manifest(
                root,
                component_paths[component],
                expected_schema=expected_schema,
            )
            _VALIDATORS[component](payload)
            if component == "budget" and family == "TERMINAL_BENCH_2_1":
                try:
                    parse_runtime_cost_contract(payload.get("runtime_cost_contract"))
                except RuntimeCostContractError as exc:
                    raise MechanismExecutionFreezeError(
                        "Terminal-Bench mechanism budget requires frozen runtime cost contract"
                    ) from exc
            payloads[component] = payload
            if component == "executor_manifest":
                entrypoint, entrypoint_rel = _repo_file(root, payload["entrypoint_path"])
                if sha256_file(entrypoint) != _sha(
                    "executor.entrypoint_sha256", payload.get("entrypoint_sha256")
                ):
                    raise MechanismExecutionFreezeError("executor entrypoint bytes differ from frozen SHA-256")
                if entrypoint_rel not in payload.get("argv", []):
                    raise MechanismExecutionFreezeError("executor argv entrypoint is non-canonical")
            if component == "observation_provider_manifest":
                implementation, implementation_rel = _repo_file(root, payload["implementation_path"])
                if sha256_file(implementation) != _sha(
                    "observation provider implementation_sha256",
                    payload.get("implementation_sha256"),
                ):
                    raise MechanismExecutionFreezeError(
                        "observation provider implementation bytes differ from frozen SHA-256"
                    )
                if implementation_rel not in payload.get("argv", []):
                    raise MechanismExecutionFreezeError(
                        "observation provider argv implementation is non-canonical"
                    )
            components.append(FrozenComponent(
                component=component,
                path=rel,
                sha256=sha256_file(path),
                bytes=path.stat().st_size,
                schema=str(payload["schema"]),
            ))
    except MechanismExecutionFreezeError:
        raise
    except Exception as exc:
        raise _translate(exc) from exc

    if family == "TERMINAL_BENCH_2_1":
        environment = payloads["environment"]
        if environment.get("family_id") != family:
            raise MechanismExecutionFreezeError("environment family differs from mechanism family")
        if _sha(
            "environment materialization_reference_digest",
            environment.get("materialization_reference_digest"),
        ) != reference_digest:
            raise MechanismExecutionFreezeError("environment materialization reference mismatch")
        if _sha(
            "environment task_manifest_sha256",
            environment.get("task_manifest_sha256"),
        ) != task_manifest:
            raise MechanismExecutionFreezeError("environment task population mismatch")
        try:
            population = verify_terminal_sandbox_environment(
                repository_root=root,
                environment=environment,
            )
        except TerminalSandboxAuthorityError as exc:
            raise MechanismExecutionFreezeError(
                f"Terminal sandbox authority replay failed: {exc}"
            ) from exc
        try:
            expected_count = int(binding.get("expected_task_count"))
        except (TypeError, ValueError) as exc:
            raise MechanismExecutionFreezeError("materialization expected_task_count malformed") from exc
        if population.expected_task_count != expected_count:
            raise MechanismExecutionFreezeError("sandbox image population task count mismatch")

    runtime = payloads["benchmark_runtime_manifest"]
    if str(runtime.get("family_id", "")).strip() != family:
        raise MechanismExecutionFreezeError("benchmark runtime family differs from mechanism family")
    runtime_env = str(runtime.get("root_environment_variable", "")).strip()
    allowed_env = payloads["executor_manifest"].get("allowed_environment_variables")
    if not isinstance(allowed_env, list) or runtime_env not in allowed_env:
        raise MechanismExecutionFreezeError(
            "executor allow-list must include benchmark runtime root variable"
        )

    actions = payloads["action_catalog_manifest"].get("actions")
    models = payloads["model_manifest"].get("models")
    prices = payloads["pricing_snapshot"].get("entries")
    if not isinstance(actions, list) or not isinstance(models, list) or not isinstance(prices, list):
        raise MechanismExecutionFreezeError("action/model/pricing population missing")
    model_ids = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in models if isinstance(row, Mapping)
    }
    price_ids = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in prices if isinstance(row, Mapping)
    }
    action_model_ids = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in actions if isinstance(row, Mapping)
    }
    if price_ids != model_ids:
        raise MechanismExecutionFreezeError("pricing population must equal frozen model population")
    if not action_model_ids.issubset(model_ids):
        raise MechanismExecutionFreezeError("action catalog references model outside frozen model manifest")
    try:
        statistical_plan = ProductStatisticalPlan(**dict(statistical_plan_payload or {}))
    except (TypeError, ValueError) as exc:
        raise MechanismExecutionFreezeError("invalid partition statistical plan") from exc
    mechanism = mechanism_plan or MechanismStatisticalPlan()
    component_map = {row.component: row.sha256 for row in components}
    prebaseline = sha256_bytes(canonical_json_bytes({
        "family_id": family,
        "materialization_reference_digest": reference_digest,
        "materialized_tree_sha256": materialized_tree,
        "task_manifest_digest": task_manifest,
        "statistical_plan_digest": statistical_plan.digest,
        "mechanism_plan_digest": mechanism.digest,
        "components": component_map,
        "risk_endpoint_bound": False,
    }))
    payload = {
        "family_id": family,
        "repository_commit": repository_commit,
        "repository_tree": repository_tree,
        "materialization_reference_path": reference_rel,
        "materialization_reference_digest": reference_digest,
        "materialized_tree_sha256": materialized_tree,
        "task_manifest_digest": task_manifest,
        "statistical_plan_digest": statistical_plan.digest,
        "statistical_plan": asdict(statistical_plan),
        "mechanism_plan_digest": mechanism.digest,
        "components": [asdict(row) for row in components],
        "prebaseline_comparison_digest": prebaseline,
    }
    return MechanismExecutionFreeze(
        **payload,
        freeze_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_mechanism_execution_freeze_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MechanismExecutionFreezeError("mechanism execution freeze must be a regular file")
    import json
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismExecutionFreezeError("invalid mechanism execution freeze JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise MechanismExecutionFreezeError("unexpected mechanism execution freeze schema")
    if (
        doc.get("risk_endpoint_bound") is not False
        or doc.get("risk_qualification_authorized") is not False
        or doc.get("governance_policies_bound") is not False
        or doc.get("baseline_panel_bound") is not False
        or doc.get("harness_frozen") is not False
        or doc.get("mechanism_execution_authorized") is not False
        or doc.get("product_confirmatory_execution_authorized") is not False
        or doc.get("product_promotion_authorized") is not False
    ):
        raise MechanismExecutionFreezeError("mechanism execution freeze authority boundary violated")
    rows = doc.get("components")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise MechanismExecutionFreezeError("mechanism component population missing")
    names = {str(row.get("component", "")) for row in rows}
    if names != set(COMPONENT_SCHEMAS_MECHANISM):
        raise MechanismExecutionFreezeError("mechanism freeze component population is not exact")
    if "risk_endpoint_manifest" in names:
        raise MechanismExecutionFreezeError("mechanism freeze illegally binds risk endpoint")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "repository_commit", "repository_tree",
            "materialization_reference_path", "materialization_reference_digest",
            "materialized_tree_sha256", "task_manifest_digest",
            "statistical_plan_digest", "statistical_plan", "mechanism_plan_digest",
            "components", "prebaseline_comparison_digest",
        )
    }
    observed = str(doc.get("freeze_digest", "")).strip().lower()
    if len(observed) != 64 or any(ch not in "0123456789abcdef" for ch in observed):
        raise MechanismExecutionFreezeError("freeze_digest must be lowercase SHA-256")
    if sha256_bytes(canonical_json_bytes(payload)) != observed:
        raise MechanismExecutionFreezeError("mechanism execution freeze digest mismatch")
    return doc
