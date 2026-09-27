from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum


class ExternalSourceStage(IntEnum):
    IDENTIFIED = 1
    SOURCE_VERIFIED = 2
    MATERIALIZED_VERIFIED = 3
    EXECUTED = 4


def _req(name: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} required")
    return str(value).strip()


def _sha(name: str, value: str | None) -> str:
    value = _req(name, value).lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return value


@dataclass(frozen=True, slots=True)
class ExternalSourceAuthority:
    family_id: str
    stage: ExternalSourceStage
    upstream_revision: str
    upstream_identity_digest: str
    source_verification_method: str | None = None
    source_verification_evidence_digest: str | None = None
    materialized_tree_sha256: str | None = None
    materialized_task_manifest_sha256: str | None = None
    execution_population_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_id", _req("family_id", self.family_id))
        object.__setattr__(self, "upstream_revision", _req("upstream_revision", self.upstream_revision))
        object.__setattr__(self, "upstream_identity_digest", _sha("upstream_identity_digest", self.upstream_identity_digest))
        if self.stage >= ExternalSourceStage.SOURCE_VERIFIED:
            object.__setattr__(self, "source_verification_method", _req("source_verification_method", self.source_verification_method))
            object.__setattr__(self, "source_verification_evidence_digest", _sha("source_verification_evidence_digest", self.source_verification_evidence_digest))
        elif self.source_verification_method or self.source_verification_evidence_digest:
            raise ValueError("IDENTIFIED source cannot carry verification authority")
        if self.stage >= ExternalSourceStage.MATERIALIZED_VERIFIED:
            object.__setattr__(self, "materialized_tree_sha256", _sha("materialized_tree_sha256", self.materialized_tree_sha256))
            object.__setattr__(self, "materialized_task_manifest_sha256", _sha("materialized_task_manifest_sha256", self.materialized_task_manifest_sha256))
        elif self.materialized_tree_sha256 or self.materialized_task_manifest_sha256:
            raise ValueError("source verification cannot imply local materialization")
        if self.stage >= ExternalSourceStage.EXECUTED:
            object.__setattr__(self, "execution_population_digest", _sha("execution_population_digest", self.execution_population_digest))
        elif self.execution_population_digest:
            raise ValueError("unexecuted source cannot carry execution population digest")

    @property
    def digest(self) -> str:
        payload = {
            "schema": "DGC_EXTERNAL_SOURCE_AUTHORITY_V1",
            "family_id": self.family_id,
            "stage": self.stage.name,
            "upstream_revision": self.upstream_revision,
            "upstream_identity_digest": self.upstream_identity_digest,
            "source_verification_method": self.source_verification_method,
            "source_verification_evidence_digest": self.source_verification_evidence_digest,
            "materialized_tree_sha256": self.materialized_tree_sha256,
            "materialized_task_manifest_sha256": self.materialized_task_manifest_sha256,
            "execution_population_digest": self.execution_population_digest,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def promote_source_verified(
    authority: ExternalSourceAuthority,
    *,
    verification_method: str,
    verification_evidence_digest: str,
) -> ExternalSourceAuthority:
    if authority.stage is not ExternalSourceStage.IDENTIFIED:
        raise ValueError("source verification requires IDENTIFIED stage")
    return ExternalSourceAuthority(
        family_id=authority.family_id,
        stage=ExternalSourceStage.SOURCE_VERIFIED,
        upstream_revision=authority.upstream_revision,
        upstream_identity_digest=authority.upstream_identity_digest,
        source_verification_method=verification_method,
        source_verification_evidence_digest=verification_evidence_digest,
    )


def promote_materialized_verified(
    authority: ExternalSourceAuthority,
    *,
    materialized_tree_sha256: str,
    materialized_task_manifest_sha256: str,
) -> ExternalSourceAuthority:
    if authority.stage is not ExternalSourceStage.SOURCE_VERIFIED:
        raise ValueError("materialization verification requires SOURCE_VERIFIED stage")
    return ExternalSourceAuthority(
        family_id=authority.family_id,
        stage=ExternalSourceStage.MATERIALIZED_VERIFIED,
        upstream_revision=authority.upstream_revision,
        upstream_identity_digest=authority.upstream_identity_digest,
        source_verification_method=authority.source_verification_method,
        source_verification_evidence_digest=authority.source_verification_evidence_digest,
        materialized_tree_sha256=materialized_tree_sha256,
        materialized_task_manifest_sha256=materialized_task_manifest_sha256,
    )


def promote_executed(
    authority: ExternalSourceAuthority, *, execution_population_digest: str
) -> ExternalSourceAuthority:
    if authority.stage is not ExternalSourceStage.MATERIALIZED_VERIFIED:
        raise ValueError("execution authority requires MATERIALIZED_VERIFIED stage")
    return ExternalSourceAuthority(
        family_id=authority.family_id,
        stage=ExternalSourceStage.EXECUTED,
        upstream_revision=authority.upstream_revision,
        upstream_identity_digest=authority.upstream_identity_digest,
        source_verification_method=authority.source_verification_method,
        source_verification_evidence_digest=authority.source_verification_evidence_digest,
        materialized_tree_sha256=authority.materialized_tree_sha256,
        materialized_task_manifest_sha256=authority.materialized_task_manifest_sha256,
        execution_population_digest=execution_population_digest,
    )
