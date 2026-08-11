from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cog_epistemic01_gate import _validate as _validate_current_r1
from scripts.cog_epistemic01_gate import main as _current_main


PARENT = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
R1 = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"


def _validate(parent: dict, r1: dict) -> list[str]:
    """Compatibility validator for the superseded R1 gate entry point.

    The canonical R1 schema was prospectively replaced by the later
    `TYPED_EPISTEMIC_LATTICE_R1_QUALIFIED_SYNTHETIC_NARROWED` artifact with fresh
    PRIMARY_R1/REPLICATION_R1 namespaces.  The old gate used an earlier repair schema
    and had drifted into a guaranteed false failure after that later result became
    canonical.  Preserve the parent-negative checks, then delegate all live R1 authority
    checks to `cog_epistemic01_gate._validate`.
    """
    errors: list[str] = []
    if parent.get("verdict") != "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED" or parent.get("scientific_pass") is not False:
        errors.append("parent raw non-pass drift")
    if not any("F11_LEGACY_COUNTERMODEL_COLLAPSE" in str(e) for e in parent.get("errors", [])):
        errors.append("parent F11 failure no longer preserved")
    errors.extend(_validate_current_r1(r1))
    return errors


def main() -> int:
    # Canonical artifact/checksum/self-test semantics live in cog_epistemic01_gate.py.
    # This wrapper exists only for callers that still use the historical filename.
    if not PARENT.is_file() or not R1.is_file():
        print("COG-EPISTEMIC01R-COMPAT FAIL: missing parent or R1 verdict")
        return 1
    parent = json.loads(PARENT.read_text())
    r1 = json.loads(R1.read_text())
    errors = _validate(parent, r1)
    if errors:
        print("COG-EPISTEMIC01R-COMPAT FAIL", *errors, sep="\n - ")
        return 1
    # Delegate artifact integrity and semantic mutation self-test to the canonical gate.
    return _current_main()


if __name__ == "__main__":
    raise SystemExit(main())
