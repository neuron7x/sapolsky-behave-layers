from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def _req(name: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} required")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplicationPackage:
    repo_commit: str
    environment_digest: str
    preregistration_digest: str
    task_manifest_digest: str
    model_manifest_digest: str
    scorer_digest: str
    policy_digest: str
    baseline_panel_digest: str
    statistical_plan_digest: str

    def __post_init__(self) -> None:
        for name in (
            "repo_commit", "environment_digest", "preregistration_digest",
            "task_manifest_digest", "model_manifest_digest", "scorer_digest",
            "policy_digest", "baseline_panel_digest", "statistical_plan_digest",
        ):
            object.__setattr__(self, name, _req(name, getattr(self, name)))

    @property
    def digest(self) -> str:
        return _digest(self.__dict__)


@dataclass(frozen=True, slots=True)
class IndependentReplicationResult:
    package_digest: str
    replicator_identity_digest: str
    replicator_attestation_digest: str
    raw_result_digest: str
    statistical_report_digest: str
    methodology_unchanged: bool
    quality_concordant: bool
    cost_direction_concordant: bool
    regret_concordant: bool
    independent_from_author: bool

    def __post_init__(self) -> None:
        for name in (
            "package_digest", "replicator_identity_digest", "replicator_attestation_digest",
            "raw_result_digest", "statistical_report_digest",
        ):
            object.__setattr__(self, name, _req(name, getattr(self, name)))

    @property
    def supported(self) -> bool:
        return all((
            self.methodology_unchanged,
            self.quality_concordant,
            self.cost_direction_concordant,
            self.regret_concordant,
            self.independent_from_author,
        ))


def certify_independent_replication(
    package: ReplicationPackage, result: IndependentReplicationResult
) -> str:
    if result.package_digest != package.digest:
        raise ValueError("replication result is not bound to the frozen package")
    if not result.independent_from_author:
        raise ValueError("self-replication does not satisfy independent replication")
    if not result.methodology_unchanged:
        raise ValueError("methodology-modified run requires a new replication generation")
    if not result.supported:
        raise RuntimeError("independent replication not concordant with preregistered bounds")
    return result.statistical_report_digest
