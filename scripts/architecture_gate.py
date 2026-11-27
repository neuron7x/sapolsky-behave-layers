"""Check static imports and registered loader calls in the scoped first-party source.

The scope covers cwc, nanochat and experiments/common. AST inspection cannot
establish the runtime dependency graph, including indirect loading or re-exports.
"""
from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from importlib.util import resolve_name
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("engineering/architecture_contract.json")
SOURCE_ROOTS = ("cwc", "nanochat", "experiments/common")
REQUIRED_BOUNDARIES = frozenset(SOURCE_ROOTS) | {
    "cwc/causal", "cwc/epistemics", "cwc/governance", "cwc/instrumentation", "cwc/plasticity",
}
FIRST_PARTY = frozenset({"cwc", "experiments", "nanochat", "scripts", "tasks", "tests"})
MODULE_LOADERS = frozenset({"__import__", "builtins.__import__", "importlib.import_module", "runpy.run_module"})
PATH_LOADERS = frozenset({"importlib.util.spec_from_file_location", "runpy.run_path"})
LOADER_MODULES = frozenset({"builtins", "importlib", "importlib.util", "runpy"})


def _dotted_name(value: object) -> bool:
    return isinstance(value, str) and all(part.isidentifier() for part in value.split("."))


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError(f"duplicate field: {key}")
        fields[key] = value
    return fields


def _read_contract(root: Path) -> tuple[dict[str, tuple[str, ...]], set[tuple[str, str]]]:
    contract = json.loads((root / CONTRACT).read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
    if not isinstance(contract, dict) or type(contract.get("schema_version")) is not int or contract["schema_version"] != 2:
        raise ValueError("unsupported schema_version")
    roster = contract.get("boundaries")
    if not isinstance(roster, list) or not roster:
        raise ValueError("nonempty boundary roster required")
    boundaries: dict[str, tuple[str, ...]] = {}
    for item in roster:
        if not isinstance(item, dict) or item.keys() != {"root", "allowed_prefixes"}:
            raise ValueError("invalid boundary entry fields")
        name, prefixes = item["root"], item["allowed_prefixes"]
        if not isinstance(name, str) or name in boundaries:
            raise ValueError(f"invalid or duplicate boundary root: {name!r}")
        if not isinstance(prefixes, list) or not all(_dotted_name(prefix) for prefix in prefixes):
            raise ValueError(f"{name}: allowed_prefixes must contain dotted names")
        if len(prefixes) != len(set(prefixes)) or any(prefix.split(".")[0] not in FIRST_PARTY for prefix in prefixes):
            raise ValueError(f"{name}: duplicate or out-of-scope allowed prefix")
        boundaries[name] = tuple(prefixes)

    declarations = contract.get("declared_dynamic_imports")
    if contract.keys() != {"schema_version", "boundaries", "declared_dynamic_imports"} or not isinstance(declarations, list):
        raise ValueError("explicit dynamic import inventory required")
    dynamic_imports: set[tuple[str, str]] = set()
    for item in declarations:
        if not isinstance(item, dict) or item.keys() != {"source", "module"}:
            raise ValueError("invalid dynamic import declaration fields")
        source, module = item["source"], item["module"]
        if not isinstance(source, str) or not _dotted_name(module):
            raise ValueError("invalid dynamic import declaration")
        if (source, module) in dynamic_imports:
            raise ValueError(f"duplicate dynamic import declaration: {source}: {module}")
        dynamic_imports.add((source, module))
    return boundaries, dynamic_imports


def _qualified_sources(root: Path) -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = {}
    for name in SOURCE_ROOTS:
        source_root = root / name
        if not source_root.is_dir() or source_root.is_symlink():
            raise ValueError(f"{name}: qualified source root missing or linked")
        for path in sorted(source_root.rglob("*")):
            relative = path.relative_to(root)
            if path.is_symlink() and (path.is_dir() or path.suffix == ".py"):
                raise ValueError(f"{relative}: linked source prohibited")
            if not path.is_file() or path.suffix != ".py":
                continue
            boundary = "/".join(relative.parts[:2]) if name == "cwc" and len(relative.parts) > 2 else name
            sources.setdefault(boundary, []).append(relative)
    return sources


def _imports(nodes: list[ast.AST], package: str) -> Iterator[tuple[int, str]]:
    for node in nodes:
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            for alias in node.names:
                yield node.lineno, module if alias.name == "*" else f"{module}.{alias.name}"


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
    return ""


def _loader_aliases(nodes: list[ast.AST]) -> dict[str, str]:
    aliases = {"__import__": "__import__"}
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in LOADER_MODULES:
                    bound = alias.asname or alias.name.split(".")[0]
                    aliases[bound] = alias.name if alias.asname else bound
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in LOADER_MODULES:
            for alias in node.names:
                target = f"{node.module}.{alias.name}"
                if target in MODULE_LOADERS | PATH_LOADERS | LOADER_MODULES:
                    aliases[alias.asname or alias.name] = target
    return aliases


def _dynamic_imports(nodes: list[ast.AST]) -> Iterator[tuple[int, str | None]]:
    aliases = _loader_aliases(nodes)
    for node in nodes:
        if isinstance(node, ast.Call):
            base, separator, middle = _qualified_name(node.func).partition(".")
            loader = aliases.get(base, "") + separator + middle
            if loader in MODULE_LOADERS:
                literal = node.args[0] if len(node.args) == 1 and not node.keywords else None
                target = literal.value if isinstance(literal, ast.Constant) else None
                yield node.lineno, target if isinstance(target, str) and _dotted_name(target) else None
            elif loader in PATH_LOADERS:
                yield node.lineno, None


def _permitted(module: str, allowed: tuple[str, ...]) -> bool:
    return module.split(".")[0] not in FIRST_PARTY or any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in allowed
    )


def _check_source(
    root: Path,
    path: Path,
    allowed: tuple[str, ...],
    declared: set[tuple[str, str]],
    observed: set[tuple[str, str]],
) -> list[str]:
    try:
        nodes = list(ast.walk(ast.parse((root / path).read_text(encoding="utf-8"), filename=path.as_posix())))
        edges = list(_imports(nodes, ".".join(path.parts[:-1])))
    except (OSError, ImportError, SyntaxError, UnicodeError) as exc:
        return [f"{path}: cannot resolve source imports: {exc}"]
    errors: list[str] = []
    for line, target in _dynamic_imports(nodes):
        if target is None:
            errors.append(f"{path}:{line}: unsupported dynamic import target")
            continue
        key = (path.as_posix(), target)
        observed.add(key)
        if key not in declared:
            errors.append(f"{path}:{line}: undeclared dynamic import {target}")
        edges.append((line, target))
    errors.extend(
        f"{path}:{line}: forbidden cross-boundary import {module}"
        for line, module in edges
        if not _permitted(module, allowed)
    )
    return errors


def validate(root: Path = ROOT) -> list[str]:
    try:
        boundaries, declared = _read_contract(root)
        sources = _qualified_sources(root)
    except (OSError, ValueError) as exc:
        return [f"{CONTRACT}: invalid contract or source inventory: {exc}"]

    missing = (REQUIRED_BOUNDARIES | sources.keys()) - boundaries.keys()
    empty_or_unknown = boundaries.keys() - sources.keys()
    if missing or empty_or_unknown:
        return [
            *(f"{CONTRACT}: missing boundary {name}" for name in sorted(missing)),
            *(f"{CONTRACT}: boundary root has no qualified source: {name}" for name in sorted(empty_or_unknown)),
        ]
    observed: set[tuple[str, str]] = set()
    errors = [
        error
        for boundary, paths in sorted(sources.items())
        for path in paths
        for error in _check_source(root, path, boundaries[boundary], declared, observed)
    ]
    errors.extend(f"{CONTRACT}: unused dynamic import declaration: {source}: {module}" for source, module in sorted(declared - observed))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ARCHITECTURE-FAIL: {error}")
        return 1
    print("ARCHITECTURE: PASS (scoped static imports and registered loader calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
