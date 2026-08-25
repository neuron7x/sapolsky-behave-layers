from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_external_replay import CHECK_HANDLERS
from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_inactive_p19_external_verification_plan_document,
    load_p19_external_verification_plan,
)
from cwc.governance.p19_external_verifier_regression import (
    current_repository_identity,
    current_runtime_digest,
    current_test_manifest_digest,
)

SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_FREEZE_READINESS_V1"


class P19ExternalVerifierFreezeReadinessError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P19ExternalVerifierFreezeReadinessError(
            f"git command failed: {' '.join(args)}"
        ) from exc


def _tracked_clean(root: Path, rel: str) -> None:
    try:
        observed = _git(root, "ls-files", "--error-unmatch", "--", rel)
    except P19ExternalVerifierFreezeReadinessError as exc:
        raise P19ExternalVerifierFreezeReadinessError(
            f"verifier freeze subject is not Git-tracked: {rel}"
        ) from exc
    if observed != rel:
        raise P19ExternalVerifierFreezeReadinessError(
            f"verifier freeze subject Git identity is ambiguous: {rel}"
        )
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "--", rel)
    if status:
        raise P19ExternalVerifierFreezeReadinessError(
            f"verifier freeze subject is dirty: {rel}"
        )


@dataclass(frozen=True, slots=True)
class P19ExternalVerifierFreezeReadiness:
    source_commit: str
    source_tree: str
    candidate_plan_digest: str
    runtime_manifest_digest: str
    test_manifest_digest: str
    method_map_digest: str
    runtime_dependency_count: int
    regression_test_count: int
    exact_check_count: int
    all_freeze_subjects_tracked_clean: bool
    canonical_plan_present: bool
    canonical_plan_matches_candidate: bool
    ready_to_freeze: bool
    readiness_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "activation_authorized": False,
            "product_qualification_authorized": False,
        }


def build_p19_external_verifier_freeze_readiness(
    *,
    repository_root: Path,
) -> P19ExternalVerifierFreezeReadiness:
    root = Path(repository_root).resolve()
    source_commit, source_tree = current_repository_identity(root)

    subjects = (
        VERIFIER_ENTRYPOINT,
        *VERIFIER_RUNTIME_DEPENDENCIES,
        *REGRESSION_TEST_FILES,
        "scripts/dgc_freeze_p19_external_verification_plan.py",
        "scripts/dgc_materialize_inactive_p19_external_verification_plan.py",
    )
    if len(set(subjects)) != len(subjects):
        raise P19ExternalVerifierFreezeReadinessError("verifier freeze subject population contains duplicates")
    for rel in subjects:
        _tracked_clean(root, rel)

    if set(CHECK_HANDLERS) != set(CHECK_METHOD_IDS):
        raise P19ExternalVerifierFreezeReadinessError(
            "external replay handler population differs from frozen method identity map"
        )

    candidate = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(CHECK_HANDLERS)),
    )
    if candidate.get("activation_authorized") is not False:
        raise P19ExternalVerifierFreezeReadinessError("candidate inactive plan authorized activation")
    if candidate.get("product_qualification_authorized") is not False:
        raise P19ExternalVerifierFreezeReadinessError("candidate inactive plan authorized product qualification")

    method_map_digest = sha256_bytes(canonical_json_bytes(CHECK_METHOD_IDS))
    canonical = root / CANONICAL_PLAN_PATH
    canonical_present = canonical.is_file() and not canonical.is_symlink()
    canonical_matches = False
    if canonical_present:
        _tracked_clean(root, CANONICAL_PLAN_PATH)
        verified = load_p19_external_verification_plan(
            canonical,
            repository_root=root,
            require_active=False,
        )
        canonical_matches = (
            verified.plan_digest == candidate.get("plan_digest")
            and verified.activation_authorized is False
        )
        if not canonical_matches:
            raise P19ExternalVerifierFreezeReadinessError(
                "canonical Plan V4 exists but differs from current inactive candidate"
            )

    payload = {
        "source_commit": source_commit,
        "source_tree": source_tree,
        "candidate_plan_digest": str(candidate["plan_digest"]),
        "runtime_manifest_digest": current_runtime_digest(root),
        "test_manifest_digest": current_test_manifest_digest(root),
        "method_map_digest": method_map_digest,
        "runtime_dependency_count": len(VERIFIER_RUNTIME_DEPENDENCIES),
        "regression_test_count": len(REGRESSION_TEST_FILES),
        "exact_check_count": len(CHECK_METHOD_IDS),
        "all_freeze_subjects_tracked_clean": True,
        "canonical_plan_present": canonical_present,
        "canonical_plan_matches_candidate": canonical_matches,
        "ready_to_freeze": not canonical_present or canonical_matches,
    }
    return P19ExternalVerifierFreezeReadiness(
        **payload,
        readiness_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def readiness_bytes(authority: P19ExternalVerifierFreezeReadiness) -> bytes:
    return canonical_json_bytes(authority.document) + b"\n"
