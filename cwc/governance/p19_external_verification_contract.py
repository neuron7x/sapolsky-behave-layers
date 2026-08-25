from __future__ import annotations

from pathlib import Path

from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS

CHECK_METHOD_IDS: dict[str, str] = {
    "REPOSITORY_IDENTITY": "DGC_P19_EXTERNAL_REPOSITORY_IDENTITY_V1",
    "THEOREM_AND_PLAN_IDENTITY": "DGC_P19_EXTERNAL_THEOREM_AND_PLAN_IDENTITY_V1",
    "SUBJECT_ROOT_REHASH": "DGC_P19_EXTERNAL_SUBJECT_ROOT_REHASH_V1",
    "P19_SEAL_REBUILD": "DGC_P19_EXTERNAL_P19_SEAL_REBUILD_V1",
    "PRIMARY_P9_RAW_REPLAY": "DGC_P19_EXTERNAL_PRIMARY_P9_RAW_REPLAY_V1",
    "GENERALIZATION_G1_G5_RAW_REPLAY": "DGC_P19_EXTERNAL_GENERALIZATION_G1_G5_RAW_REPLAY_V1",
    "FAULT_TOLERANCE_RAW_REPLAY": "DGC_P19_EXTERNAL_FAULT_TOLERANCE_RAW_REPLAY_V1",
    "INDEPENDENT_REPLICATION_RAW_REPLAY": "DGC_P19_EXTERNAL_INDEPENDENT_REPLICATION_RAW_REPLAY_V1",
}

VERIFIER_ENTRYPOINT = "scripts/dgc_external_p19_verifier.py"
VERIFIER_OPERATOR_DEPENDENCIES = (
    "scripts/dgc_run_p19_external_verifier_regression.py",
    "scripts/dgc_freeze_p19_external_verification_plan.py",
    "scripts/dgc_materialize_inactive_p19_external_verification_plan.py",
    "scripts/dgc_materialize_activated_p19_external_verification_plan.py",
    "scripts/dgc_authorize_p19_external_verifier.py",
    "scripts/dgc_build_verifier_regression_attestation.py",
    "scripts/dgc_p19_external_verifier_freeze_readiness.py",
)

# Fail conservative: the external verifier delegates scientific semantics to canonical
# governance builders. Freeze the complete governance Python tree plus every canonical
# operator script that can materialize regression/freeze/activation evidence. Any
# semantic or operator mutation therefore invalidates the runtime digest and requires
# a new pre-outcome freeze + regression activation cycle.
_GOVERNANCE_DIR = Path(__file__).resolve().parent
_REPOSITORY_ROOT = _GOVERNANCE_DIR.parents[1]
_GOVERNANCE_DEPENDENCIES = tuple(
    sorted(
        path.resolve().relative_to(_REPOSITORY_ROOT).as_posix()
        for path in _GOVERNANCE_DIR.rglob("*.py")
        if path.is_file() and not path.is_symlink()
    )
)
VERIFIER_RUNTIME_DEPENDENCIES = tuple(
    sorted((*_GOVERNANCE_DEPENDENCIES, *VERIFIER_OPERATOR_DEPENDENCIES))
)

REGRESSION_TEST_FILES = (
    "tests/test_dgc_p19_external_verification_contract.py",
    "tests/test_dgc_p19_external_python_runtime.py",
    "tests/test_dgc_p19_external_verification_plan.py",
    "tests/test_dgc_p19_external_verification_transition.py",
    "tests/test_dgc_p19_external_verifier_regression.py",
    "tests/test_dgc_p19_external_verifier_activation.py",
    "tests/test_dgc_p19_external_verifier_freeze_readiness.py",
    "tests/test_dgc_p19_external_replay.py",
    "tests/test_dgc_p19_verification_report.py",
    "tests/test_dgc_p19_verification_attestation.py",
    "tests/test_dgc_p19_evidence_root.py",
    "tests/test_dgc_p19_verifier_policy_canonical_identity.py",
    "tests/test_dgc_qualified_evidence_bundle.py",
    "tests/test_dgc_qualified_evidence_bundle_v3.py",
)
CANONICAL_REGRESSION_COMMAND = (
    "python",
    "-m",
    "pytest",
    "-q",
    *REGRESSION_TEST_FILES,
)

if set(CHECK_METHOD_IDS) != REQUIRED_CHECKS:
    raise RuntimeError("P19 external verification method map differs from required check population")
if len(set(CHECK_METHOD_IDS.values())) != len(REQUIRED_CHECKS):
    raise RuntimeError("P19 external verification method identities must be unique")
if not VERIFIER_RUNTIME_DEPENDENCIES:
    raise RuntimeError("P19 external verifier runtime dependency closure is empty")
for required in (
    "cwc/governance/p19_external_replay.py",
    "cwc/governance/p19_external_verification_contract.py",
    "cwc/governance/p19_external_verification_transition.py",
    "cwc/governance/p19_external_verifier_freeze_readiness.py",
    "cwc/governance/p19_external_python_runtime.py",
    *VERIFIER_OPERATOR_DEPENDENCIES,
):
    if required not in VERIFIER_RUNTIME_DEPENDENCIES:
        raise RuntimeError(f"P19 external verifier runtime dependency missing: {required}")
if len(set(VERIFIER_RUNTIME_DEPENDENCIES)) != len(VERIFIER_RUNTIME_DEPENDENCIES):
    raise RuntimeError("P19 external verifier runtime dependencies must be unique")
if len(set(VERIFIER_OPERATOR_DEPENDENCIES)) != len(VERIFIER_OPERATOR_DEPENDENCIES):
    raise RuntimeError("P19 external verifier operator dependencies must be unique")
if len(set(REGRESSION_TEST_FILES)) != len(REGRESSION_TEST_FILES):
    raise RuntimeError("P19 external verifier regression test files must be unique")
