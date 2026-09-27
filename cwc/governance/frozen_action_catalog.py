from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import sha256_file


class FrozenActionCatalogError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FrozenActionCatalogError(f"{name} must be lowercase SHA-256")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FrozenActionCatalogError("action catalog path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise FrozenActionCatalogError(f"action catalog symlink path rejected: {rel.as_posix()}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FrozenActionCatalogError("action catalog path escapes repository root") from exc
    if not resolved.is_file():
        raise FrozenActionCatalogError("action catalog file missing")
    return resolved, rel.as_posix()


@dataclass(frozen=True, slots=True)
class FrozenActionSpec:
    action_id: str
    harbor_agent: str
    harbor_agent_argument: str
    harbor_model_argument: str
    agent_version: str
    provider: str
    model_id: str
    model_version: str


@dataclass(frozen=True, slots=True)
class FrozenActionCatalog:
    component_sha256: str
    actions: tuple[FrozenActionSpec, ...]

    def resolve(self, action_id: str) -> FrozenActionSpec:
        target = str(action_id).strip()
        matches = [row for row in self.actions if row.action_id == target]
        if len(matches) != 1:
            raise FrozenActionCatalogError(f"unknown frozen action_id: {target}")
        return matches[0]


def load_frozen_action_catalog(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
) -> FrozenActionCatalog:
    root = Path(repository_root).resolve()
    rows = execution_freeze.get("components")
    if not isinstance(rows, list):
        raise FrozenActionCatalogError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "action_catalog_manifest"
    ]
    if len(matches) != 1:
        raise FrozenActionCatalogError("exactly one frozen action catalog component required")
    row = matches[0]
    path, rel = _safe_file(root, row.get("path"))
    component_sha = _sha("action catalog component sha256", row.get("sha256"))
    if sha256_file(path) != component_sha:
        raise FrozenActionCatalogError("action catalog bytes differ from execution freeze")
    if rel != row.get("path"):
        raise FrozenActionCatalogError("action catalog path is non-canonical")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FrozenActionCatalogError("invalid action catalog JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "DGC_ACTION_CATALOG_MANIFEST_V1":
        raise FrozenActionCatalogError("unexpected action catalog schema")
    raw = payload.get("actions")
    if not isinstance(raw, list) or len(raw) < 2:
        raise FrozenActionCatalogError("action catalog requires at least two actions")
    actions: list[FrozenActionSpec] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise FrozenActionCatalogError("invalid action catalog row")
        fields = {
            name: str(item.get(name, "")).strip()
            for name in (
                "action_id", "harbor_agent", "harbor_agent_argument",
                "harbor_model_argument", "agent_version",
                "provider", "model_id", "model_version",
            )
        }
        if any(not value for value in fields.values()):
            raise FrozenActionCatalogError("action catalog row has empty identity field")
        actions.append(FrozenActionSpec(**fields))
    if [row.action_id for row in actions] != sorted({row.action_id for row in actions}):
        raise FrozenActionCatalogError("action catalog action ids are not sorted and unique")
    return FrozenActionCatalog(component_sha256=component_sha, actions=tuple(actions))
