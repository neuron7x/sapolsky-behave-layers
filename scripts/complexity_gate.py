"""Enforce explicit algorithmic complexity budgets for critical functions."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("engineering/complexity_budgets.json")
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.comprehension)


def _metrics(path: Path, function: str) -> tuple[int, int] | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function:
            cyclomatic = 1 + sum(isinstance(child, BRANCH_NODES) for child in ast.walk(node))
            cyclomatic += sum(
                max(0, len(child.values) - 1)
                for child in ast.walk(node)
                if isinstance(child, ast.BoolOp)
            )
            statements = sum(isinstance(child, ast.stmt) for child in ast.walk(node)) - 1
            return cyclomatic, statements
    return None


def validate(root: Path = ROOT) -> list[str]:
    try:
        contract: dict[str, Any] = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{CONTRACT}: invalid contract: {exc}"]
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for budget in contract.get("budgets", []):
        key = (budget["path"], budget["function"])
        if key in seen:
            errors.append(f"{budget['path']}:{budget['function']}: duplicate budget")
            continue
        seen.add(key)
        path = root / budget["path"]
        metrics = _metrics(path, budget["function"]) if path.is_file() else None
        if metrics is None:
            errors.append(f"{budget['path']}:{budget['function']}: target missing")
            continue
        cyclomatic, statements = metrics
        if cyclomatic > budget["max_cyclomatic"]:
            errors.append(
                f"{budget['path']}:{budget['function']}: cyclomatic {cyclomatic} "
                f"> {budget['max_cyclomatic']}"
            )
        if statements > budget["max_statements"]:
            errors.append(
                f"{budget['path']}:{budget['function']}: statements {statements} "
                f"> {budget['max_statements']}"
            )
    if len(seen) < 5:
        errors.append(f"{CONTRACT}: at least five critical functions must be budgeted")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"COMPLEXITY-FAIL: {error}")
        return 1
    print("COMPLEXITY: PASS (critical-function budgets preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
