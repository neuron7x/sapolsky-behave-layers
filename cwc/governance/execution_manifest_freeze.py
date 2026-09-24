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
_GIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")
_OCI_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MUTABLE_VERSION_ALIASES = frozenset({"latest", "default", "current", "stable", "production", "prod"})

COMPONENT_SCHEMAS = {
    "action_catalog_manifest": "DGC_ACTION_CATALOG_MANIFEST_V1",
    "benchmark_runtime_manifest": "DGC_BENCHMARK_RUNTIME_MANIFEST_V1",
    "executor_manifest": "DGC_EXECUTOR_MANIFEST_V1",
    "model_manifest": "DGC_MODEL_MANIFEST_V1",
    "observation_provider_manifest": "DGC_OBSERVATION_PROVIDER_MANIFEST_V1",
    "prompt_policy": "DGC_PROMPT_POLICY_V1",
    "tool_manifest": "DGC_TOOL_MANIFEST_V1",
    "environment": "DGC_ENVIRONMENT_MANIFEST_V1",
    "budget": "DGC_BUDGET_MANIFEST_V1",
    "pricing_snapshot": "DGC_PRICING_SNAPSHOT_V1",
    "risk_endpoint_manifest": "DGC_RISK_ENDPOINT_MANIFEST_V1",
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
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ExecutionManifestError(f"manifest symlink path rejected: {rel.as_posix()}")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ExecutionManifestError("manifest path escapes repository root") from exc
    if not path.is_file():
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


def _validate_benchmark_runtime(payload: Mapping[str, object]) -> None:
    _req("benchmark runtime family_id", payload.get("family_id"))
    _req("benchmark runtime runtime_name", payload.get("runtime_name"))
    version = _req("benchmark runtime runtime_version", payload.get("runtime_version"))
    if version.lower() in _MUTABLE_VERSION_ALIASES:
        raise ExecutionManifestError("mutable benchmark runtime version alias is prohibited")
    _req("benchmark runtime repository", payload.get("repository"))
    commit = _req("benchmark runtime repository_commit", payload.get("repository_commit")).lower()
    tree = _req("benchmark runtime repository_tree", payload.get("repository_tree")).lower()
    lock_blob = _req("benchmark runtime lock_file_blob_oid", payload.get("lock_file_blob_oid")).lower()
    if _GIT_OID_RE.fullmatch(commit) is None:
        raise ExecutionManifestError("benchmark runtime repository_commit must be a Git object id")
    if _GIT_OID_RE.fullmatch(tree) is None:
        raise ExecutionManifestError("benchmark runtime repository_tree must be a Git tree id")
    if _GIT_OID_RE.fullmatch(lock_blob) is None:
        raise ExecutionManifestError("benchmark runtime lock_file_blob_oid must be a Git blob id")
    lock_path = Path(_req("benchmark runtime lock_file_path", payload.get("lock_file_path")))
    if lock_path.is_absolute() or ".." in lock_path.parts:
        raise ExecutionManifestError("benchmark runtime lock_file_path must be repository-relative")
    invocation = payload.get("invocation")
    if (
        not isinstance(invocation, list)
        or not invocation
        or not all(isinstance(x, str) and x.strip() for x in invocation)
    ):
        raise ExecutionManifestError("benchmark runtime invocation must be a non-empty string list")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in invocation):
        raise ExecutionManifestError("benchmark runtime invocation contains control characters")
    env_name = _req(
        "benchmark runtime root_environment_variable",
        payload.get("root_environment_variable"),
    )
    if not env_name.replace("_", "").isalnum() or not env_name[0].isalpha():
        raise ExecutionManifestError("benchmark runtime root_environment_variable is invalid")
    if payload.get("local_materialization_required") is not True:
        raise ExecutionManifestError("benchmark runtime must require local materialization")


def _validate_action_catalog(payload: Mapping[str, object]) -> None:
    actions = payload.get("actions")
    if not isinstance(actions, list) or len(actions) < 2:
        raise ExecutionManifestError("action catalog requires at least two actions")
    ids: list[str] = []
    for row in actions:
        if not isinstance(row, Mapping):
            raise ExecutionManifestError("invalid action catalog row")
        action_id = _req("action.action_id", row.get("action_id"))
        _req("action.harbor_agent", row.get("harbor_agent"))
        _req("action.harbor_agent_argument", row.get("harbor_agent_argument"))
        _req("action.harbor_model_argument", row.get("harbor_model_argument"))
        agent_version = _req("action.agent_version", row.get("agent_version"))
        provider = _req("action.provider", row.get("provider"))
        model_id = _req("action.model_id", row.get("model_id"))
        model_version = _req("action.model_version", row.get("model_version"))
        if agent_version.lower() in _MUTABLE_VERSION_ALIASES:
            raise ExecutionManifestError("mutable agent version alias is prohibited")
        if model_version.lower() in _MUTABLE_VERSION_ALIASES:
            raise ExecutionManifestError("mutable action model version alias is prohibited")
        ids.append(action_id)
    if ids != sorted(set(ids)):
        raise ExecutionManifestError("action catalog must be sorted by unique action_id")


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
    seen: set[tuple[str, str, str]] = set()
    for row in entries:
        if not isinstance(row, Mapping):
            raise ExecutionManifestError("invalid pricing row")
        provider = _req("pricing.provider", row.get("provider"))
        model_id = _req("pricing.model_id", row.get("model_id"))
        model_version = _req("pricing.model_version", row.get("model_version"))
        if _req("pricing.currency", row.get("currency")) != "USD":
            raise ExecutionManifestError("pricing currency must be USD")
        _req("pricing.source_uri", row.get("source_uri"))
        identity = (provider, model_id, model_version)
        if identity in seen:
            raise ExecutionManifestError("duplicate pricing model identity")
        seen.add(identity)
        for field in (
            "input_per_million",
            "cached_input_per_million",
            "cache_write_per_million",
            "long_cache_write_per_million",
            "output_per_million",
        ):
            _finite_nonnegative(f"pricing.{field}", row.get(field))


def _validate_scorer(payload: Mapping[str, object]) -> None:
    _req("scorer.version", payload.get("version"))
    _sha("scorer.implementation_sha256", payload.get("implementation_sha256"))


def _validate_risk_endpoint(payload: Mapping[str, object]) -> None:
    if _req("risk endpoint name", payload.get("endpoint_name")) != "catastrophic_regret":
        raise ExecutionManifestError("risk endpoint must bind catastrophic_regret")
    if _req("risk endpoint scale", payload.get("scale")) != "[0,1]":
        raise ExecutionManifestError("risk endpoint scale must be [0,1]")
    _req("risk endpoint semantics_version", payload.get("semantics_version"))
    if payload.get("protocol") != RISK_ENDPOINT_PROTOCOL:
        raise ExecutionManifestError("risk endpoint protocol identity mismatch")
    if payload.get("request_schema") != RISK_ENDPOINT_REQUEST_SCHEMA:
        raise ExecutionManifestError("risk endpoint request schema identity mismatch")
    if payload.get("response_schema") != RISK_ENDPOINT_RESPONSE_SCHEMA:
        raise ExecutionManifestError("risk endpoint response schema identity mismatch")
    implementation = _req("risk endpoint implementation_path", payload.get("implementation_path"))
    _sha("risk endpoint implementation_sha256", payload.get("implementation_sha256"))
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ExecutionManifestError("risk endpoint argv must be a non-empty string list")
    if implementation not in argv:
        raise ExecutionManifestError("risk endpoint argv must contain the frozen implementation path")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv):
        raise ExecutionManifestError("risk endpoint argv contains forbidden control characters")
    timeout = _finite_nonnegative("risk endpoint timeout_seconds", payload.get("timeout_seconds"))
    if timeout <= 0:
        raise ExecutionManifestError("risk endpoint timeout_seconds must be > 0")
    source_fields = payload.get("source_fields")
    if not isinstance(source_fields, list) or not source_fields or not all(
        isinstance(x, str) and x.strip() for x in source_fields
    ):
        raise ExecutionManifestError("risk endpoint source_fields must be a non-empty string list")
    if [x.strip() for x in source_fields] != sorted(set(x.strip() for x in source_fields)):
        raise ExecutionManifestError("risk endpoint source_fields must be sorted and unique")
    if payload.get("policy_outcome_independent_definition") is not True:
        raise ExecutionManifestError("risk endpoint definition must be frozen independently of policy outcomes")
    if payload.get("post_outcome_relabeling_allowed") is not False:
        raise ExecutionManifestError("post-outcome risk relabeling must be prohibited")
    if payload.get("network_access_allowed") is not False:
        raise ExecutionManifestError("risk endpoint execution must prohibit network access")
    if implementation.startswith("/") or ".." in Path(implementation).parts:
        raise ExecutionManifestError("risk endpoint implementation path must be repository-relative")


OBSERVATION_PROVIDER_PROTOCOL = "DGC_PREOUTCOME_OBSERVATION_PROTOCOL_V1"
OBSERVATION_PROVIDER_REQUEST_SCHEMA = "DGC_PREOUTCOME_OBSERVATION_REQUEST_V1"
OBSERVATION_PROVIDER_RESPONSE_SCHEMA = "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1"

RISK_ENDPOINT_PROTOCOL = "DGC_RISK_ENDPOINT_EXECUTION_PROTOCOL_V1"
RISK_ENDPOINT_REQUEST_SCHEMA = "DGC_RISK_ENDPOINT_REQUEST_V1"
RISK_ENDPOINT_RESPONSE_SCHEMA = "DGC_RISK_ENDPOINT_RESPONSE_V1"

POLICY_PROTOCOL = "DGC_GOVERNANCE_POLICY_EXECUTION_PROTOCOL_V1"
POLICY_REQUEST_SCHEMA = "DGC_POLICY_DECISION_REQUEST_V1"
POLICY_RESPONSE_SCHEMA = "DGC_POLICY_DECISION_RESPONSE_V1"
POLICY_STATE_PROTOCOL = "STATE_IN_REQUEST_ONLY"

EXECUTOR_PROTOCOL = "DGC_FROZEN_UNIT_EXECUTOR_PROTOCOL_V1"
EXECUTOR_REQUEST_SCHEMA = "DGC_UNIT_EXECUTION_REQUEST_V1"
EXECUTOR_RESPONSE_SCHEMA = "DGC_UNIT_EXECUTION_RESPONSE_V1"


_FORBIDDEN_POLICY_OBSERVATIONS = frozenset({
    "accepted_success",
    "catastrophic_regret",
    "confirmatory_label",
    "final_reward",
    "ground_truth",
    "test_outcome",
    "verifier_result",
})


def policy_action_catalog_digest(action_ids: object) -> str:
    if not isinstance(action_ids, list) or len(action_ids) < 2:
        raise ExecutionManifestError("policy action_ids must contain at least two actions")
    normalized = [str(x).strip() for x in action_ids]
    if any(not x for x in normalized) or normalized != sorted(set(normalized)):
        raise ExecutionManifestError("policy action_ids must be sorted, unique and non-empty")
    return sha256_bytes(canonical_json_bytes({"action_ids": normalized}))


def policy_observation_contract_digest(fields: object) -> str:
    if not isinstance(fields, list) or not fields:
        raise ExecutionManifestError("policy observation_fields must be non-empty")
    normalized = [str(x).strip() for x in fields]
    if any(not x for x in normalized) or normalized != sorted(set(normalized)):
        raise ExecutionManifestError("policy observation_fields must be sorted, unique and non-empty")
    forbidden = sorted(set(normalized) & _FORBIDDEN_POLICY_OBSERVATIONS)
    if forbidden:
        raise ExecutionManifestError(
            f"policy observation contract leaks confirmatory outcomes: {forbidden}"
        )
    return sha256_bytes(canonical_json_bytes({"observation_fields": normalized}))


def _validate_policy_config(
    path: Path,
    *,
    policy_id: str,
    action_catalog_digest: str,
    observation_contract_digest: str,
) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionManifestError(f"{policy_id}: invalid governance config JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "DGC_GOVERNANCE_POLICY_CONFIG_V1":
        raise ExecutionManifestError(f"{policy_id}: governance config schema mismatch")
    if _req("governance config policy_id", payload.get("policy_id")) != policy_id:
        raise ExecutionManifestError(f"{policy_id}: governance config policy id mismatch")
    if policy_action_catalog_digest(payload.get("action_ids")) != action_catalog_digest:
        raise ExecutionManifestError(f"{policy_id}: action catalog digest does not match config")
    if policy_observation_contract_digest(payload.get("observation_fields")) != observation_contract_digest:
        raise ExecutionManifestError(f"{policy_id}: observation contract digest does not match config")


def _validate_observation_provider(payload: Mapping[str, object]) -> None:
    if payload.get("protocol") != OBSERVATION_PROVIDER_PROTOCOL:
        raise ExecutionManifestError("observation provider protocol identity mismatch")
    if payload.get("request_schema") != OBSERVATION_PROVIDER_REQUEST_SCHEMA:
        raise ExecutionManifestError("observation provider request schema identity mismatch")
    if payload.get("response_schema") != OBSERVATION_PROVIDER_RESPONSE_SCHEMA:
        raise ExecutionManifestError("observation provider response schema identity mismatch")
    implementation = _req("observation provider implementation_path", payload.get("implementation_path"))
    _sha("observation provider implementation_sha256", payload.get("implementation_sha256"))
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ExecutionManifestError("observation provider argv must be a non-empty string list")
    if implementation not in argv:
        raise ExecutionManifestError("observation provider argv must contain the frozen implementation path")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv):
        raise ExecutionManifestError("observation provider argv contains forbidden control characters")
    timeout = _finite_nonnegative("observation provider timeout_seconds", payload.get("timeout_seconds"))
    if timeout <= 0:
        raise ExecutionManifestError("observation provider timeout_seconds must be > 0")
    fields = payload.get("output_fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(x, str) and x.strip() for x in fields):
        raise ExecutionManifestError("observation provider output_fields must be a non-empty string list")
    normalized = [x.strip() for x in fields]
    if normalized != sorted(set(normalized)):
        raise ExecutionManifestError("observation provider output_fields must be sorted and unique")
    if payload.get("network_access_allowed") is not False:
        raise ExecutionManifestError("observation provider network access must be prohibited")
    if payload.get("confirmatory_label_access") is not False:
        raise ExecutionManifestError("observation provider confirmatory label access must be prohibited")
    if payload.get("post_outcome_access_allowed") is not False:
        raise ExecutionManifestError("observation provider post-outcome access must be prohibited")
    if implementation.startswith("/") or ".." in Path(implementation).parts:
        raise ExecutionManifestError("observation provider implementation path must be repository-relative")


def _validate_executor(payload: Mapping[str, object]) -> None:
    if payload.get("protocol") != EXECUTOR_PROTOCOL:
        raise ExecutionManifestError("executor protocol identity mismatch")
    if payload.get("request_schema") != EXECUTOR_REQUEST_SCHEMA:
        raise ExecutionManifestError("executor request schema identity mismatch")
    if payload.get("response_schema") != EXECUTOR_RESPONSE_SCHEMA:
        raise ExecutionManifestError("executor response schema identity mismatch")
    entrypoint = _req("executor.entrypoint_path", payload.get("entrypoint_path"))
    _sha("executor.entrypoint_sha256", payload.get("entrypoint_sha256"))
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ExecutionManifestError("executor argv must be a non-empty string list")
    if entrypoint not in argv:
        raise ExecutionManifestError("executor argv must contain the frozen entrypoint path")
    if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv):
        raise ExecutionManifestError("executor argv contains forbidden control characters")
    timeout = _finite_nonnegative("executor.timeout_seconds", payload.get("timeout_seconds"))
    if timeout <= 0:
        raise ExecutionManifestError("executor timeout_seconds must be > 0")
    allowed = payload.get("allowed_environment_variables")
    if not isinstance(allowed, list) or not all(isinstance(x, str) and x.strip() and "=" not in x for x in allowed):
        raise ExecutionManifestError("executor allowed_environment_variables must be a string list")
    normalized = [x.strip() for x in allowed]
    if normalized != sorted(set(normalized)):
        raise ExecutionManifestError("executor environment allow-list must be sorted and unique")


_VALIDATORS = {
    "action_catalog_manifest": _validate_action_catalog,
    "benchmark_runtime_manifest": _validate_benchmark_runtime,
    "executor_manifest": _validate_executor,
    "model_manifest": _validate_model,
    "observation_provider_manifest": _validate_observation_provider,
    "prompt_policy": _validate_prompt,
    "tool_manifest": _validate_tools,
    "environment": _validate_environment,
    "budget": _validate_budget,
    "pricing_snapshot": _validate_pricing,
    "risk_endpoint_manifest": _validate_risk_endpoint,
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
    implementation_path: str
    implementation_sha256: str
    config_path: str
    config_sha256: str
    protocol: str
    argv: tuple[str, ...]
    timeout_seconds: float
    action_catalog_digest: str
    observation_contract_digest: str


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
    component_payloads: dict[str, dict[str, object]] = {}
    for component in sorted(COMPONENT_SCHEMAS):
        payload, path, rel = _json_manifest(root, component_paths[component], expected_schema=COMPONENT_SCHEMAS[component])
        _VALIDATORS[component](payload)
        component_payloads[component] = payload
        if component == "executor_manifest":
            entrypoint, entrypoint_rel = _repo_file(root, payload["entrypoint_path"])
            if sha256_file(entrypoint) != _sha("executor.entrypoint_sha256", payload.get("entrypoint_sha256")):
                raise ExecutionManifestError("executor entrypoint bytes differ from frozen SHA-256")
            if entrypoint_rel not in payload.get("argv", []):
                raise ExecutionManifestError("executor argv entrypoint is not canonical repository-relative path")
        if component == "observation_provider_manifest":
            implementation, implementation_rel = _repo_file(root, payload["implementation_path"])
            if sha256_file(implementation) != _sha(
                "observation provider implementation_sha256", payload.get("implementation_sha256")
            ):
                raise ExecutionManifestError("observation provider implementation bytes differ from frozen SHA-256")
            if implementation_rel != str(payload.get("implementation_path")):
                raise ExecutionManifestError("observation provider implementation path is non-canonical")
            if implementation_rel not in payload.get("argv", []):
                raise ExecutionManifestError(
                    "observation provider argv implementation is not canonical repository-relative path"
                )
        if component == "risk_endpoint_manifest":
            implementation, implementation_rel = _repo_file(root, payload["implementation_path"])
            if sha256_file(implementation) != _sha(
                "risk endpoint implementation_sha256", payload.get("implementation_sha256")
            ):
                raise ExecutionManifestError("risk endpoint implementation bytes differ from frozen SHA-256")
            if implementation_rel != str(payload.get("implementation_path")):
                raise ExecutionManifestError("risk endpoint implementation path is non-canonical")
            if implementation_rel not in payload.get("argv", []):
                raise ExecutionManifestError("risk endpoint argv implementation is not canonical repository-relative path")
        components.append(FrozenComponent(
            component=component,
            path=rel,
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            schema=COMPONENT_SCHEMAS[component],
        ))

    runtime_family = str(component_payloads["benchmark_runtime_manifest"].get("family_id", "")).strip()
    if runtime_family != family:
        raise ExecutionManifestError("benchmark runtime family differs from execution family")
    runtime_env_name = str(
        component_payloads["benchmark_runtime_manifest"].get("root_environment_variable", "")
    ).strip()
    executor_allowed_env = component_payloads["executor_manifest"].get(
        "allowed_environment_variables"
    )
    if not isinstance(executor_allowed_env, list) or runtime_env_name not in executor_allowed_env:
        raise ExecutionManifestError(
            "executor environment allow-list must include benchmark runtime root variable"
        )

    action_rows = component_payloads["action_catalog_manifest"].get("actions")
    model_rows = component_payloads["model_manifest"].get("models")
    pricing_rows = component_payloads["pricing_snapshot"].get("entries")
    if not isinstance(action_rows, list) or not isinstance(model_rows, list) or not isinstance(pricing_rows, list):
        raise ExecutionManifestError("action/model/pricing populations missing after validation")
    model_identities = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in model_rows
        if isinstance(row, Mapping)
    }
    pricing_identities = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in pricing_rows
        if isinstance(row, Mapping)
    }
    if pricing_identities != model_identities:
        raise ExecutionManifestError(
            "pricing snapshot must bind exactly the frozen model provider/id/version population"
        )
    action_model_identities = {
        (str(row["provider"]), str(row["model_id"]), str(row["model_version"]))
        for row in action_rows
        if isinstance(row, Mapping)
    }
    if not action_model_identities.issubset(model_identities):
        raise ExecutionManifestError(
            "action catalog references model identities outside the frozen model manifest"
        )
    frozen_action_ids = [str(row["action_id"]) for row in action_rows if isinstance(row, Mapping)]
    frozen_action_catalog_digest = policy_action_catalog_digest(frozen_action_ids)

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
        if payload.get("protocol") != POLICY_PROTOCOL:
            raise ExecutionManifestError(f"{policy_id}: governance execution protocol mismatch")
        if payload.get("request_schema") != POLICY_REQUEST_SCHEMA:
            raise ExecutionManifestError(f"{policy_id}: governance request schema mismatch")
        if payload.get("response_schema") != POLICY_RESPONSE_SCHEMA:
            raise ExecutionManifestError(f"{policy_id}: governance response schema mismatch")
        if payload.get("state_protocol") != POLICY_STATE_PROTOCOL:
            raise ExecutionManifestError(f"{policy_id}: hidden policy state is prohibited")
        if payload.get("network_access_allowed") is not False:
            raise ExecutionManifestError(f"{policy_id}: governance policy network access prohibited")
        if payload.get("confirmatory_label_access") is not False:
            raise ExecutionManifestError(f"{policy_id}: confirmatory label access prohibited")
        argv_raw = payload.get("argv")
        if (
            not isinstance(argv_raw, list)
            or not argv_raw
            or not all(isinstance(x, str) and x.strip() for x in argv_raw)
        ):
            raise ExecutionManifestError(f"{policy_id}: governance argv malformed")
        if any(any(ch in x for ch in ("\x00", "\n", "\r")) for x in argv_raw):
            raise ExecutionManifestError(f"{policy_id}: governance argv contains control characters")
        timeout_seconds = _finite_nonnegative(
            f"{policy_id}.timeout_seconds", payload.get("timeout_seconds")
        )
        if timeout_seconds <= 0:
            raise ExecutionManifestError(f"{policy_id}: governance timeout must be > 0")
        action_catalog_digest = _sha(
            f"{policy_id}.action_catalog_digest", payload.get("action_catalog_digest")
        )
        observation_contract_digest = _sha(
            f"{policy_id}.observation_contract_digest", payload.get("observation_contract_digest")
        )
        implementation, implementation_rel = _repo_file(root, payload.get("implementation_path"))
        config, config_rel = _repo_file(root, payload.get("config_path"))
        implementation_sha = _sha("governance implementation_sha256", payload.get("implementation_sha256"))
        config_sha = _sha("governance config_sha256", payload.get("config_sha256"))
        if sha256_file(implementation) != implementation_sha:
            raise ExecutionManifestError(f"{policy_id}: governance implementation bytes differ from declared SHA-256")
        if sha256_file(config) != config_sha:
            raise ExecutionManifestError(f"{policy_id}: governance config bytes differ from declared SHA-256")
        _validate_policy_config(
            config,
            policy_id=policy_id,
            action_catalog_digest=action_catalog_digest,
            observation_contract_digest=observation_contract_digest,
        )
        if implementation_rel not in argv_raw or config_rel not in argv_raw:
            raise ExecutionManifestError(
                f"{policy_id}: governance argv must bind canonical implementation and config paths"
            )
        policies.append(FrozenGovernancePolicy(
            policy_id=policy_id,
            path=rel,
            sha256=sha256_file(path),
            implementation_path=implementation_rel,
            implementation_sha256=implementation_sha,
            config_path=config_rel,
            config_sha256=config_sha,
            protocol=POLICY_PROTOCOL,
            argv=tuple(argv_raw),
            timeout_seconds=timeout_seconds,
            action_catalog_digest=action_catalog_digest,
            observation_contract_digest=observation_contract_digest,
        ))

    if len({row.action_catalog_digest for row in policies}) != 1:
        raise ExecutionManifestError("all governance policies must share one frozen action catalog")
    if any(row.action_catalog_digest != frozen_action_catalog_digest for row in policies):
        raise ExecutionManifestError(
            "governance policy action catalog differs from global frozen action catalog"
        )
    if len({row.observation_contract_digest for row in policies}) != 1:
        raise ExecutionManifestError("all governance policies must share one admissible observation contract")
    frozen_observation_contract_digest = next(iter({row.observation_contract_digest for row in policies}))
    provider_fields = component_payloads["observation_provider_manifest"].get("output_fields")
    if policy_observation_contract_digest(provider_fields) != frozen_observation_contract_digest:
        raise ExecutionManifestError(
            "observation provider output fields differ from governance observation contract"
        )

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
