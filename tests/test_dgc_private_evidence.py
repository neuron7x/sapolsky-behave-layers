from __future__ import annotations

import importlib
import json
import os
import stat
import sys
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance.evidence_closure import ClosureError
from cwc.governance.materialization_closure import _write_immutable as write_reference
from scripts import dgc_admit_terminal_bench_trial as admission_cli
from scripts.dgc_run_p19_external_verifier_regression import _write_immutable as write_regression

# Exercise the actual evidence writers, including the idempotent runtime reference.
WRITER_MODULES = (
    "cwc.governance.materialization_closure",
    "scripts.dgc_audit_ccf_oracle",
    "scripts.dgc_authorize_confirmatory_execution",
    "scripts.dgc_authorize_executed_p9",
    "scripts.dgc_authorize_fault_tolerance",
    "scripts.dgc_authorize_generalization",
    "scripts.dgc_authorize_generalization_axis",
    "scripts.dgc_authorize_generalization_scientific",
    "scripts.dgc_authorize_independent_replication",
    "scripts.dgc_authorize_p19_external_verifier",
    "scripts.dgc_authorize_p9_scientific",
    "scripts.dgc_build_family_p19",
    "scripts.dgc_build_global_product_qualification_v4",
    "scripts.dgc_build_global_product_qualification_v5",
    "scripts.dgc_build_p19_verification_check_receipt",
    "scripts.dgc_build_p19_verification_report",
    "scripts.dgc_build_verifier_regression_attestation",
    "scripts.dgc_external_p19_verifier",
    "scripts.dgc_freeze_ccf_spec",
    "scripts.dgc_freeze_fault_injection_spec",
    "scripts.dgc_freeze_final_harness",
    "scripts.dgc_freeze_generalization_registry",
    "scripts.dgc_freeze_p19_external_verification_plan",
    "scripts.dgc_make_p19_verification_attestation",
    "scripts.dgc_materialize_activated_p19_external_verification_plan",
    "scripts.dgc_materialize_inactive_p19_external_verification_plan",
    "scripts.dgc_run_p19_external_verifier_regression",
)
PAYLOAD = b'{"evidence":"<raw>&\\n"}\n\x00\xff'


@pytest.fixture(autouse=True)
def ci_umask() -> Iterator[None]:
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.fixture(params=WRITER_MODULES)
def writer(request: pytest.FixtureRequest) -> Callable[[Path, bytes], None]:
    module = importlib.import_module(request.param)
    if request.param == "scripts.dgc_run_p19_external_verifier_regression":
        return partial(module._write_immutable, allow_empty=False)
    return module._write_immutable


def test_new_evidence_is_private_and_byte_exact(writer, tmp_path: Path):
    path = tmp_path / "new" / "evidence.bin"
    writer(path, PAYLOAD)
    assert path.read_bytes() == PAYLOAD
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_conflicting_evidence_is_not_replaced(writer, tmp_path: Path):
    path = tmp_path / "evidence.bin"
    path.write_bytes(PAYLOAD)
    path.chmod(0o444)
    with pytest.raises((FileExistsError, ClosureError)):
        writer(path, b"replacement")
    assert path.read_bytes() == PAYLOAD
    assert stat.S_IMODE(path.stat().st_mode) == 0o444


@pytest.mark.parametrize("dangling", (False, True))
def test_symlink_is_not_followed(writer, tmp_path: Path, dangling: bool):
    target = tmp_path / "target.bin"
    if not dangling:
        target.write_bytes(PAYLOAD)
    path = tmp_path / "evidence.bin"
    path.symlink_to(target)
    with pytest.raises((FileExistsError, ClosureError)):
        writer(path, b"replacement")
    assert path.is_symlink()
    if dangling:
        assert not target.exists()
    else:
        assert target.read_bytes() == PAYLOAD


@pytest.mark.parametrize("mode", (0o444, 0o600, 0o644))
def test_identical_reference_reuse_preserves_existing_bytes_and_mode(tmp_path: Path, mode: int):
    path = tmp_path / "reference.bin"
    path.write_bytes(PAYLOAD)
    path.chmod(mode)
    before = path.stat()
    write_reference(path, PAYLOAD)
    after = path.stat()
    assert path.read_bytes() == PAYLOAD
    assert stat.S_IMODE(after.st_mode) == mode
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


def test_empty_optional_regression_output_is_private(tmp_path: Path):
    path = tmp_path / "stderr.bin"
    write_regression(path, b"", allow_empty=True)
    assert path.read_bytes() == b""
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_empty_required_regression_output_is_rejected(tmp_path: Path):
    path = tmp_path / "stdout.bin"
    with pytest.raises(RuntimeError, match="empty required regression subject"):
        write_regression(path, b"", allow_empty=False)
    assert not path.exists()


def test_admission_cli_writes_private_immutable_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    document = {"task_id": "task-a", "raw": "<raw>&\n"}
    admitted = SimpleNamespace(
        document=document,
        task_id="task-a",
        quality=1.0,
        agent_metered_cost_usd=0.25,
        evidence_digest="a" * 64,
    )
    monkeypatch.setattr(admission_cli, "admit_terminal_bench_trial", lambda **kwargs: admitted)
    output = tmp_path / "new" / "admission.json"
    monkeypatch.setattr(sys, "argv", [
        "dgc_admit_terminal_bench_trial.py", "--trial-root", str(tmp_path / "trial"),
        "--task-id", "task-a", "--output", str(output),
    ])
    expected = json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    assert admission_cli.main() == 0
    assert output.read_bytes() == expected
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError, match="immutable"):
        admission_cli.main()
    assert output.read_bytes() == expected
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
