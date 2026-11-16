from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/secret_scan_container.sh"
HEAD = "a" * 40
CLEAN_LOG = "5:22PM INF 1 commits scanned.\n5:22PM INF no leaks found\n"


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output: str = CLEAN_LOG,
    scanner_exit: int = 0,
    fsck_exit: int = 0,
    head: str = HEAD,
    commits: str = "1",
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(
        '#!/bin/sh\nset -eu\ncase "$*" in\n'
        '  "rev-parse --verify HEAD") printf "%s\\n" "$TEST_HEAD" ;;\n'
        '  "rev-list --count --all") printf "%s\\n" "$TEST_COMMITS" ;;\n'
        '  "fsck --full --no-reflogs --no-dangling") exit "$TEST_FSCK_EXIT" ;;\n'
        '  *) exit 99 ;;\nesac\n'
    )
    scanner = bin_dir / "gitleaks"
    scanner.write_text(
        '#!/bin/sh\nset -eu\n'
        'printf "%s\\n" "$@" > "$TEST_ARGS"\n'
        'cat "$TEST_LOG" >&2\nexit "$TEST_SCANNER_EXIT"\n'
    )
    git.chmod(0o700)
    scanner.chmod(0o700)
    log = tmp_path / "scanner.log"
    log.write_text(output)
    for name, value in {
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "TEST_HEAD": head,
        "TEST_COMMITS": commits,
        "TEST_FSCK_EXIT": str(fsck_exit),
        "TEST_ARGS": str(tmp_path / "scanner-args.txt"),
        "TEST_LOG": str(log),
        "TEST_SCANNER_EXIT": str(scanner_exit),
    }.items():
        monkeypatch.setenv(name, value)
    return subprocess.run(
        ["sh", str(HELPER), HEAD],
        capture_output=True,
        text=True,
        check=False,
        umask=0o022,
    )


def test_success_requires_real_work_and_retains_redaction_and_history_scope(tmp_path: Path, monkeypatch):
    result = _run(tmp_path, monkeypatch)
    assert result.returncode == 0, result.stderr
    assert CLEAN_LOG in result.stdout
    arguments = (tmp_path / "scanner-args.txt").read_text().splitlines()
    assert arguments[0] == "git"
    assert {"--redact", "--no-color", "--log-opts=--all"} <= set(arguments)


@pytest.mark.parametrize(
    "output",
    [
        "5:22PM ERR [git] fatal: unable to read object\n" + CLEAN_LOG,
        "5:22PM FTL scanner failed\n" + CLEAN_LOG,
        "5:22PM PNC scanner failed\n" + CLEAN_LOG,
        "5:22PM INF 0 commits scanned.\n5:22PM INF no leaks found\n",
        "5:22PM INF no leaks found\n",
        CLEAN_LOG + CLEAN_LOG,
        "",
    ],
    ids=["error", "fatal", "panic", "zero-work", "missing-summary", "duplicate-summary", "empty-log"],
)
def test_scanner_exit_zero_cannot_hide_incomplete_or_failed_scan(tmp_path: Path, monkeypatch, output: str):
    result = _run(tmp_path, monkeypatch, output=output)
    assert result.returncode != 0
    assert "scanner errors or missing nonzero scan evidence" in result.stderr


@pytest.mark.parametrize("scanner_exit", [1, 2, 137])
def test_scanner_failure_status_is_preserved(tmp_path: Path, monkeypatch, scanner_exit: int):
    result = _run(tmp_path, monkeypatch, scanner_exit=scanner_exit)
    assert result.returncode == scanner_exit


@pytest.mark.parametrize("failure", [{"fsck_exit": 1}, {"head": "b" * 40}, {"commits": "0"}])
def test_invalid_git_history_is_rejected_before_scanner(tmp_path: Path, monkeypatch, failure):
    result = _run(tmp_path, monkeypatch, **failure)
    assert result.returncode != 0
    assert not (tmp_path / "scanner-args.txt").exists()


def test_canonical_security_gate_executes_scanner_regressions():
    result = subprocess.run(
        ["make", "--dry-run", "-f", "Makefile.cwc", "pr-security"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "-m pytest -q tests/test_secret_scan_gate.py" in result.stdout
