from __future__ import annotations

import ast
from pathlib import Path

from scripts.truth_gate import _dotted, _literal_reason, validate


def test_dotted_name_reconstruction_is_exact() -> None:
    call = ast.parse("pytest.mark.skipif(flag, reason='missing evidence')").body[0].value
    assert isinstance(call, ast.Call)
    assert _dotted(call.func) == "pytest.mark.skipif"
    assert _literal_reason(call) == "missing evidence"


def test_real_repository_passes_the_anti_green_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate(root) == []
