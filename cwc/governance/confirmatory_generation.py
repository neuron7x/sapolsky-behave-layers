from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Mapping, Protocol

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _sha256(name: str, value: str) -> str:
    value = str(value).strip()
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _git_oid(name: str, value: str) -> str:
    value = str(value).strip()
    if _GIT_OID_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase Git object id")
    return value


def _canonical_task_manifest(task_ids: tuple[str, ...]) -> str:
    tasks = tuple(sorted(str(x).strip() for x in task_ids if str(x).strip()))
    if not tasks or len(tasks) != len(set(tasks)):
        raise ValueError("task_ids must be non-empty and unique")
    return _digest(tasks)


class _SourceAuthority(Protocol):
    family_id: str
    stage: object
    digest: str
    materialized_tree_sha256: str | None
    materialized_task_manifest_sha256: str | None


class _Harness(Protocol):
    task_manifest_digest: str
    statistical_plan_digest: str
    baseline_panel_digest: str
    governance_policy_digest: str
    comparison_frame_digest: str
    full_digest: str


class _BaselinePanel(Protocol):
    executable_frozen: bool
    digest: str


class _StatisticalPlan(Protocol):
    digest: str
    per_claim_alpha: float
    target_power: float


class _TrialSizing(Protocol):
    required_trials_per_task: int
    per_claim_alpha: float
    target_power: float


class _DistributedSpec(Protocol):
    task_ids: tuple[str, ...]
    policy_ids: tuple[str, ...]
    replicates: int
    harness_digest: str
    statistical_plan_digest: str
    digest: str


class _Completion(Protocol):
    spec_digest: str
    expected_units: int
    committed_units: int
    total_cost_usd: float
    audit_root_digest: str
    result_population_digest: str
    complete: bool


@dataclass(frozen=True, slots=True)
class PolicyHarnessBinding:
    policy_id: str
    governance_policy_digest: str
    harness_full_digest: str

    def __post_init__(self) -> None:
        policy = str(self.policy_id).strip()
        if not policy:
            raise ValueError("policy_id required")
        object.__setattr__(self, "policy_id", policy)
        object.__setattr__(
            self, "governance_policy_digest", _sha256("governance_policy_digest", self.governance_policy_digest)
        )
        object.__setattr__(
            self, "harness_full_digest", _sha256("harness_full_digest", self.harness_full_digest)
        )


@dataclass(frozen=True, slots=True)
class ConfirmatoryGenerationRoot:
    generation_id: str
    family_id: str
    repo_commit_oid: str
    repo_tree_oid: str
    source_authority_digest: str
    materialized_tree_sha256: str
    task_manifest_sha256: str
    comparison_frame_digest: str
    baseline_panel_digest: str
    statistical_plan_digest: str
    trial_sizing_digest: str
    distributed_spec_digest: str
    policy_bindings: tuple[PolicyHarnessBinding, ...]
    expected_work_units: int
    root_digest: str


@dataclass(frozen=True, slots=True)
class ConfirmatoryCompletionCertificate:
    generation_root_digest: str
    distributed_spec_digest: str
    result_population_digest: str
    audit_root_digest: str
    expected_work_units: int
    committed_work_units: int
    total_cost_usd: float
    execution_population_digest: str
    complete: bool


def freeze_confirmatory_generation(
    *,
    generation_id: str,
    repo_commit_oid: str,
    repo_tree_oid: str,
    source_authority: _SourceAuthority,
    baseline_panel: _BaselinePanel,
    statistical_plan: _StatisticalPlan,
    trial_sizing: _TrialSizing,
    policy_harnesses: Mapping[str, _Harness],
    distributed_spec: _DistributedSpec,
) -> ConfirmatoryGenerationRoot:
    generation = str(generation_id).strip()
    if not generation:
        raise ValueError("generation_id required")
    commit = _git_oid("repo_commit_oid", repo_commit_oid)
    tree = _git_oid("repo_tree_oid", repo_tree_oid)

    stage_name = getattr(getattr(source_authority, "stage", None), "name", None)
    if stage_name is None:
        stage_name = str(getattr(source_authority, "stage", ""))
    if stage_name != "MATERIALIZED_VERIFIED":
        raise ValueError("confirmatory freeze requires MATERIALIZED_VERIFIED external source authority")

    family_id = str(source_authority.family_id).strip()
    if not family_id:
        raise ValueError("source family_id required")
    source_digest = _sha256("source_authority_digest", source_authority.digest)
    materialized_tree = _sha256(
        "materialized_tree_sha256", str(source_authority.materialized_tree_sha256 or "")
    )
    source_task_manifest = _sha256(
        "materialized_task_manifest_sha256",
        str(source_authority.materialized_task_manifest_sha256 or ""),
    )

    if not bool(baseline_panel.executable_frozen):
        raise ValueError("B0-B3 baseline panel must be executable-frozen before confirmatory freeze")
    baseline_digest = _sha256("baseline_panel_digest", baseline_panel.digest)
    plan_digest = _sha256("statistical_plan_digest", statistical_plan.digest)

    sizing_trials = int(trial_sizing.required_trials_per_task)
    if sizing_trials <= 0:
        raise ValueError("trial sizing must require at least one trial per task")
    if distributed_spec.replicates != sizing_trials:
        raise ValueError("distributed replicate count does not match frozen cluster-aware trial sizing")
    if not math.isclose(
        float(trial_sizing.per_claim_alpha), float(statistical_plan.per_claim_alpha), rel_tol=0, abs_tol=1e-15
    ):
        raise ValueError("trial sizing alpha does not match frozen statistical plan")
    if not math.isclose(
        float(trial_sizing.target_power), float(statistical_plan.target_power), rel_tol=0, abs_tol=1e-15
    ):
        raise ValueError("trial sizing target power does not match frozen statistical plan")
    trial_sizing_digest = _digest(
        {
            "required_trials_per_task": sizing_trials,
            "per_claim_alpha": float(trial_sizing.per_claim_alpha),
            "target_power": float(trial_sizing.target_power),
        }
    )

    tasks = tuple(distributed_spec.task_ids)
    observed_task_manifest = _canonical_task_manifest(tasks)
    if observed_task_manifest != source_task_manifest:
        raise ValueError("distributed task population does not match materialized workload task manifest")

    policies = tuple(sorted(str(x).strip() for x in distributed_spec.policy_ids))
    if not policies or len(policies) != len(set(policies)):
        raise ValueError("distributed policy_ids must be non-empty and unique")
    harness_map = {str(k).strip(): v for k, v in policy_harnesses.items()}
    if set(harness_map) != set(policies):
        raise ValueError("policy harness bindings must match distributed policy population exactly")

    comparison_digests: set[str] = set()
    governance_digests: set[str] = set()
    bindings: list[PolicyHarnessBinding] = []
    for policy_id in policies:
        harness = harness_map[policy_id]
        task_digest = _sha256("harness.task_manifest_digest", harness.task_manifest_digest)
        if task_digest != source_task_manifest:
            raise ValueError(f"{policy_id}: harness task manifest differs from materialized workload")
        if _sha256("harness.statistical_plan_digest", harness.statistical_plan_digest) != plan_digest:
            raise ValueError(f"{policy_id}: harness statistical plan digest mismatch")
        if _sha256("harness.baseline_panel_digest", harness.baseline_panel_digest) != baseline_digest:
            raise ValueError(f"{policy_id}: harness baseline panel digest mismatch")
        comparison = _sha256("comparison_frame_digest", harness.comparison_frame_digest)
        governance = _sha256("governance_policy_digest", harness.governance_policy_digest)
        full_digest = _sha256("harness_full_digest", harness.full_digest)
        comparison_digests.add(comparison)
        governance_digests.add(governance)
        bindings.append(PolicyHarnessBinding(policy_id, governance, full_digest))

    if len(comparison_digests) != 1:
        raise ValueError("all policy arms must share one frozen controlled-comparison frame")
    if len(governance_digests) != len(policies):
        raise ValueError("each policy arm must bind a distinct governance policy digest")
    comparison_frame = next(iter(comparison_digests))

    if _sha256("distributed_spec.harness_digest", distributed_spec.harness_digest) != comparison_frame:
        raise ValueError("distributed spec is not bound to the frozen comparison frame")
    if _sha256("distributed_spec.statistical_plan_digest", distributed_spec.statistical_plan_digest) != plan_digest:
        raise ValueError("distributed spec statistical plan digest mismatch")
    distributed_digest = _sha256("distributed_spec.digest", distributed_spec.digest)

    expected_work_units = len(tasks) * len(policies) * sizing_trials
    if expected_work_units <= 0:
        raise ValueError("empty confirmatory work population")

    ordered_bindings = tuple(sorted(bindings, key=lambda x: x.policy_id))
    root_payload = {
        "schema": "DGC_CONFIRMATORY_GENERATION_ROOT_V1",
        "generation_id": generation,
        "family_id": family_id,
        "repo_commit_oid": commit,
        "repo_tree_oid": tree,
        "source_authority_digest": source_digest,
        "materialized_tree_sha256": materialized_tree,
        "task_manifest_sha256": source_task_manifest,
        "comparison_frame_digest": comparison_frame,
        "baseline_panel_digest": baseline_digest,
        "statistical_plan_digest": plan_digest,
        "trial_sizing_digest": trial_sizing_digest,
        "distributed_spec_digest": distributed_digest,
        "policy_bindings": [
            (b.policy_id, b.governance_policy_digest, b.harness_full_digest)
            for b in ordered_bindings
        ],
        "expected_work_units": expected_work_units,
    }
    return ConfirmatoryGenerationRoot(
        generation_id=generation,
        family_id=family_id,
        repo_commit_oid=commit,
        repo_tree_oid=tree,
        source_authority_digest=source_digest,
        materialized_tree_sha256=materialized_tree,
        task_manifest_sha256=source_task_manifest,
        comparison_frame_digest=comparison_frame,
        baseline_panel_digest=baseline_digest,
        statistical_plan_digest=plan_digest,
        trial_sizing_digest=trial_sizing_digest,
        distributed_spec_digest=distributed_digest,
        policy_bindings=ordered_bindings,
        expected_work_units=expected_work_units,
        root_digest=_digest(root_payload),
    )


def certify_confirmatory_completion(
    root: ConfirmatoryGenerationRoot,
    completion: _Completion,
) -> ConfirmatoryCompletionCertificate:
    if _sha256("completion.spec_digest", completion.spec_digest) != root.distributed_spec_digest:
        raise ValueError("completion certificate belongs to a different distributed spec")
    if not bool(completion.complete):
        raise ValueError("completion certificate must be complete")
    if completion.expected_units != root.expected_work_units:
        raise ValueError("completion expected_units mismatch frozen generation")
    if completion.committed_units != root.expected_work_units:
        raise ValueError("full frozen work population was not committed")
    result_population = _sha256(
        "completion.result_population_digest", completion.result_population_digest
    )
    audit_root = _sha256("completion.audit_root_digest", completion.audit_root_digest)
    total_cost = float(completion.total_cost_usd)
    if not math.isfinite(total_cost) or total_cost < 0:
        raise ValueError("completion total_cost_usd must be finite and >= 0")
    execution_population_digest = _digest(
        {
            "generation_root_digest": root.root_digest,
            "result_population_digest": result_population,
            "audit_root_digest": audit_root,
            "expected_work_units": root.expected_work_units,
            "committed_work_units": completion.committed_units,
            "total_cost_usd": total_cost,
        }
    )
    return ConfirmatoryCompletionCertificate(
        generation_root_digest=root.root_digest,
        distributed_spec_digest=root.distributed_spec_digest,
        result_population_digest=result_population,
        audit_root_digest=audit_root,
        expected_work_units=root.expected_work_units,
        committed_work_units=completion.committed_units,
        total_cost_usd=total_cost,
        execution_population_digest=execution_population_digest,
        complete=True,
    )
