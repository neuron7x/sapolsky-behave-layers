"""Enforce directional package boundaries from a machine-readable contract."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("engineering/architecture_contract.json")


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def validate(root: Path = ROOT) -> list[str]:
    contract_path = root / CONTRACT
    try:
        contract: dict[str, Any] = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{CONTRACT}: invalid contract: {exc}"]
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append(f"{CONTRACT}: unsupported schema_version")
    for boundary in contract.get("boundaries", []):
        boundary_root = root / boundary["root"]
        namespace = boundary["internal_namespace"]
        allowed = tuple(boundary["allowed_prefixes"])
        if not boundary_root.is_dir():
            errors.append(f"{boundary['root']}: boundary root missing")
            continue
        for path in sorted(boundary_root.rglob("*.py")):
            for line, module in _imports(path):
                if (
                    module == namespace or module.startswith(f"{namespace}.")
                ) and not any(module == prefix or module.startswith(f"{prefix}.") for prefix in allowed):
                    rel = path.relative_to(root)
                    errors.append(f"{rel}:{line}: forbidden cross-boundary import {module}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ARCHITECTURE-FAIL: {error}")
        return 1
    print("ARCHITECTURE: PASS (declared package boundaries are preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
