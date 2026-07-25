"""Reject network-dependent canonical evidence and reproduction code."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("engineering/hermeticity_contract.json")


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def validate(root: Path = ROOT) -> list[str]:
    try:
        contract: dict[str, Any] = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{CONTRACT}: invalid contract: {exc}"]
    errors: list[str] = []
    forbidden_imports = tuple(contract["forbidden_import_prefixes"])
    forbidden_calls = tuple(contract["forbidden_call_prefixes"])
    for rel, requirements in contract["canonical_scripts"].items():
        path = root / rel
        if not path.is_file():
            errors.append(f"{rel}: canonical script missing")
            continue
        text = path.read_text(encoding="utf-8")
        for token in requirements["required_tokens"]:
            if token not in text:
                errors.append(f"{rel}: hermeticity token missing: {token}")
        tree = ast.parse(text, filename=rel)
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_imports):
                    errors.append(f"{rel}:{getattr(node, 'lineno', 0)}: forbidden network import {module}")
            if isinstance(node, ast.Call):
                name = _dotted(node.func)
                if any(name.startswith(prefix) for prefix in forbidden_calls):
                    errors.append(f"{rel}:{node.lineno}: forbidden network call {name}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"HERMETICITY-FAIL: {error}")
        return 1
    print("HERMETICITY: PASS (canonical evidence path is offline and seed-locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
