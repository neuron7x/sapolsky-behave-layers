from __future__ import annotations

from pathlib import Path
from typing import Mapping

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.global_product_qualification_v4 import FamilyP19VerificationInputV4
from cwc.governance.global_product_qualification_v5 import (
    build_global_product_qualification_authority_v5,
    verify_global_product_qualification_authority_v5_document,
)
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.p19_evidence_root import (
    build_family_p19_evidence_root,
    verify_family_p19_evidence_root_document,
)
from cwc.governance.p19_verifier_policy import CANONICAL_POLICY_PATH
from cwc.governance.qualification_closure import _stage_evidence_file


def _repo_file(ledger: EvidenceClosureLedger, value: Path, *, label: str) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else ledger.repository_root / value
    if candidate.is_symlink():
        raise ClosureError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError(f"{label} path escapes repository") from exc
    if not resolved.is_file():
        raise ClosureError(f"{label} must be a regular file")
    return resolved, rel.as_posix()


def close_p19_sealed(
    ledger: EvidenceClosureLedger,
    *,
    p19_authority_path: Path,
    primary_anytime_p9_authority_path: Path,
    primary_ccf_oracle_audit_authority_path: Path,
    subject_roots: Mapping[str, Path],
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "P19_SEALED":
        raise ClosureError("P19_SEALED is not the next admissible stage")
    declared_path, rel = _repo_file(ledger, p19_authority_path, label="family P19 evidence root")
    try:
        declared = verify_family_p19_evidence_root_document(declared_path)
        rebuilt = build_family_p19_evidence_root(
            ledger=ledger,
            primary_anytime_p9_authority_path=Path(primary_anytime_p9_authority_path),
            primary_ccf_oracle_audit_authority_path=Path(primary_ccf_oracle_audit_authority_path),
            subject_roots=subject_roots,
        )
    except RuntimeError as exc:
        raise ClosureError("family P19 raw-subject replay failed") from exc
    if rebuilt.p19_digest != declared.get("p19_digest"):
        raise ClosureError("declared family P19 differs from raw-subject/ledger recomputation")
    if not rebuilt.family_evidence_complete:
        raise ClosureError("family P19 evidence root is incomplete")
    if declared.get("global_product_qualification_authorized") is not False:
        raise ClosureError("family P19 illegally authorizes global product qualification")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(declared_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="P19_SEALED",
        commands=(),
        evidence=(artifact,),
    ))


def close_product_qualified(
    ledger: EvidenceClosureLedger,
    *,
    global_product_authority_path: Path,
    peer_family_p19_path: Path,
    source_registry_path: Path,
    own_p19_verification_input: FamilyP19VerificationInputV4,
    peer_p19_verification_input: FamilyP19VerificationInputV4,
    p19_verifier_policy_path: Path = Path(CANONICAL_POLICY_PATH),
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "PRODUCT_QUALIFIED":
        raise ClosureError("PRODUCT_QUALIFIED is not the next admissible stage")
    declared_path, rel = _repo_file(
        ledger, global_product_authority_path, label="global product qualification V5 authority"
    )
    peer_path, _ = _repo_file(ledger, peer_family_p19_path, label="peer family P19 evidence root")
    own_p19_path, _, _ = _stage_evidence_file(ledger, stage="P19_SEALED")
    registry_path, _ = _repo_file(ledger, source_registry_path, label="canonical source authority registry")
    policy_path, _ = _repo_file(ledger, p19_verifier_policy_path, label="P19 verifier trust policy")
    try:
        declared = verify_global_product_qualification_authority_v5_document(declared_path)
        own = verify_family_p19_evidence_root_document(own_p19_path)
        peer = verify_family_p19_evidence_root_document(peer_path)
        rebuilt = build_global_product_qualification_authority_v5(
            repository_root=ledger.repository_root,
            source_registry_path=registry_path,
            family_p19_paths=(own_p19_path, peer_path),
            family_p19_verification_inputs=(
                own_p19_verification_input,
                peer_p19_verification_input,
            ),
            p19_verifier_policy_path=policy_path,
        )
    except RuntimeError as exc:
        raise ClosureError("global two-family product qualification V5 replay failed") from exc
    if own.get("family_id") == peer.get("family_id"):
        raise ClosureError("PRODUCT_QUALIFIED requires two distinct canonical workload families")
    if rebuilt.authority_digest != declared.get("authority_digest"):
        raise ClosureError("declared global V5 authority differs from portable two-family recomputation")
    if not rebuilt.product_qualified or not rebuilt.all_family_p19_externally_verified:
        raise ClosureError("global V5 product qualification evidence/verification record is incomplete")
    if rebuilt.production_control_authorized:
        raise ClosureError("PRODUCT_QUALIFIED cannot imply production control authorization")
    if rebuilt.repository_commit != ledger.repo_commit or rebuilt.repository_tree != ledger.repo_tree:
        raise ClosureError("global V5 authority repository identity differs from promotion ledger")
    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(declared_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="PRODUCT_QUALIFIED",
        commands=(),
        evidence=(artifact,),
    ))
