"""Attack assurance controls in disposable copies and require every attack to be caught."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from scripts import (
    architecture_gate,
    build_sbom,
    complexity_gate,
    hermeticity_gate,
    inference_integrity_gate,
    dgc_verification_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def _copy_fixture(destination: Path) -> None:
    for directory in ("cwc", "nanochat", "experiments/common", "scripts", "engineering", "docs/security"):
        source = ROOT / directory
        if source.exists():
            shutil.copytree(source, destination / directory)
    shutil.copy2(ROOT / "uv.lock", destination / "uv.lock")
    shutil.copy2(ROOT / "Makefile.cwc", destination / "Makefile.cwc")


def run_attacks() -> dict[str, bool]:
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="cwc-assurance-attack-") as tmp:
        root = Path(tmp)
        _copy_fixture(root)

        breach = root / "cwc/instrumentation/breach.py"
        breach.write_text("import cwc.plasticity.optimizer\n", encoding="utf-8")
        results["cross_boundary_import"] = bool(architecture_gate.validate(root))
        breach.unlink()

        reproduce = root / "scripts/reproduce_primary.py"
        reproduce.write_text(reproduce.read_text(encoding="utf-8") + "\nimport requests\n", encoding="utf-8")
        results["network_dependency"] = bool(hermeticity_gate.validate(root))
        shutil.copy2(ROOT / "scripts/reproduce_primary.py", reproduce)

        budget_path = root / complexity_gate.CONTRACT
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
        budget["budgets"][0]["max_cyclomatic"] = 0
        budget_path.write_text(json.dumps(budget), encoding="utf-8")
        results["complexity_budget_regression"] = bool(complexity_gate.validate(root))
        shutil.copy2(ROOT / complexity_gate.CONTRACT, budget_path)

        sbom_path = root / build_sbom.DEFAULT_OUTPUT
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
        sbom["components"][0]["version"] = "0.0.0-corrupted"
        sbom_path.write_text(json.dumps(sbom), encoding="utf-8")
        results["sbom_tamper"] = bool(build_sbom.validate(root))

        engine_path = root / "nanochat/engine.py"
        engine = engine_path.read_text(encoding="utf-8")
        engine_path.write_text(
            engine.replace("validate_logits(logits)", "pass  # validation bypassed"),
            encoding="utf-8",
        )
        results["inference_validation_bypass"] = bool(inference_integrity_gate.validate(root))

        for name, killed in dgc_verification_gate.run_fault_injections().items():
            results[name.lower()] = killed
    return results


def validate() -> list[str]:
    return [f"attack survived undetected: {name}" for name, killed in run_attacks().items() if not killed]


def main() -> int:
    results = run_attacks()
    for name, killed in results.items():
        print(f"ASSURANCE-ATTACK: {'KILLED' if killed else 'SURVIVED'} {name}")
    survivors = [name for name, killed in results.items() if not killed]
    if survivors:
        print(f"ASSURANCE-ATTACK: FAIL ({len(survivors)} survivors)")
        return 1
    print(f"ASSURANCE-ATTACK: PASS ({len(results)}/{len(results)} attacks killed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
