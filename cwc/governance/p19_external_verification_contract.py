from __future__ import annotations

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
VERIFIER_RUNTIME_DEPENDENCIES = (
    "cwc/governance/p19_external_verification_contract.py",
    "cwc/governance/p19_external_replay.py",
)
REGRESSION_TEST_FILES = (
    "tests/test_dgc_p19_external_verification_plan.py",
    "tests/test_dgc_p19_external_replay.py",
    "tests/test_dgc_p19_verification_report.py",
    "tests/test_dgc_p19_verification_attestation.py",
    "tests/test_dgc_p19_evidence_root.py",
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
if len(set(VERIFIER_RUNTIME_DEPENDENCIES)) != len(VERIFIER_RUNTIME_DEPENDENCIES):
    raise RuntimeError("P19 external verifier runtime dependencies must be unique")
if len(set(REGRESSION_TEST_FILES)) != len(REGRESSION_TEST_FILES):
    raise RuntimeError("P19 external verifier regression test files must be unique")
