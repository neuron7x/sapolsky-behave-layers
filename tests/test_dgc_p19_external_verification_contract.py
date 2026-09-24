from __future__ import annotations

from pathlib import Path

from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_OPERATOR_DEPENDENCIES,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


def test_runtime_dependency_contract_equals_governance_tree_plus_operator_surface():
    root = Path(__file__).resolve().parents[1]
    governance = root / "cwc/governance"
    governance_paths = tuple(
        sorted(
            path.resolve().relative_to(root).as_posix()
            for path in governance.rglob("*.py")
            if path.is_file() and not path.is_symlink()
        )
    )
    expected = tuple(sorted((*governance_paths, *VERIFIER_OPERATOR_DEPENDENCIES)))
    assert VERIFIER_RUNTIME_DEPENDENCIES == expected
    assert "cwc/governance/p19_external_replay.py" in expected
    assert "cwc/governance/p19_external_verifier_freeze_readiness.py" in expected
    assert "cwc/governance/p19_external_python_runtime.py" in expected
    assert "scripts/dgc_run_p19_external_verifier_regression.py" in expected
    assert "scripts/dgc_authorize_p19_external_verifier.py" in expected


def test_method_identity_contract_is_exact_unique_eight_check_population():
    assert set(CHECK_METHOD_IDS) == REQUIRED_CHECKS
    assert len(CHECK_METHOD_IDS) == 8
    assert len(set(CHECK_METHOD_IDS.values())) == 8
    assert CHECK_METHOD_IDS["P19_SEAL_REBUILD"] == "DGC_P19_EXTERNAL_P19_SEAL_REBUILD_V1"


def test_runtime_operator_and_regression_contract_paths_exist_and_are_unique():
    root = Path(__file__).resolve().parents[1]
    assert (root / VERIFIER_ENTRYPOINT).is_file()
    assert len(set(VERIFIER_OPERATOR_DEPENDENCIES)) == len(VERIFIER_OPERATOR_DEPENDENCIES)
    assert all((root / rel).is_file() for rel in VERIFIER_OPERATOR_DEPENDENCIES)
    assert len(set(REGRESSION_TEST_FILES)) == len(REGRESSION_TEST_FILES)
    assert all((root / rel).is_file() for rel in REGRESSION_TEST_FILES)
