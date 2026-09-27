from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_OPENAI_SNAPSHOT_PANEL_AUTHORITY_V1"
PANEL_ID = "OPENAI_GPT_5_4_TWO_TIER_SNAPSHOT_V1"
EXPECTED = {
    "DEEP": ("gpt-5.4-mini-2026-03-17", "2026-03-17"),
    "STANDARD": ("gpt-5.4-nano-2026-03-17", "2026-03-17"),
}
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SnapshotPanelError(RuntimeError):
    pass


def _json(path: Path, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise SnapshotPanelError(f"missing regular panel manifest: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotPanelError(f"invalid JSON manifest: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise SnapshotPanelError(f"unexpected schema for {candidate}")
    if doc.get("panel_id") != PANEL_ID:
        raise SnapshotPanelError("panel_id mismatch")
    if doc.get("product_promotion_authorized") is not False:
        raise SnapshotPanelError("candidate panel cannot grant product promotion")
    return doc


def _finite_positive(name: str, value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotPanelError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise SnapshotPanelError(f"{name} must be finite and > 0")
    return parsed


@dataclass(frozen=True, slots=True)
class SnapshotPanelAuthority:
    panel_id: str
    agent: str
    agent_version: str
    action_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    model_manifest_sha256: str
    action_catalog_sha256: str
    pricing_snapshot_sha256: str
    authority_digest: str
    executable_evidence_observed: bool = False
    product_promotion_authorized: bool = False
    schema: str = SCHEMA

    @property
    def document(self) -> dict[str, object]:
        return asdict(self)


def verify_openai_snapshot_panel(
    *,
    model_manifest_path: Path,
    action_catalog_path: Path,
    pricing_snapshot_path: Path,
) -> SnapshotPanelAuthority:
    model_doc = _json(model_manifest_path, "DGC_MODEL_MANIFEST_V1")
    action_doc = _json(action_catalog_path, "DGC_ACTION_CATALOG_MANIFEST_V1")
    pricing_doc = _json(pricing_snapshot_path, "DGC_PRICING_SNAPSHOT_V1")

    raw_models = model_doc.get("models")
    raw_actions = action_doc.get("actions")
    raw_prices = pricing_doc.get("entries")
    if not isinstance(raw_models, list) or not raw_models:
        raise SnapshotPanelError("model population missing")
    if not isinstance(raw_actions, list) or not raw_actions:
        raise SnapshotPanelError("action population missing")
    if not isinstance(raw_prices, list) or not raw_prices:
        raise SnapshotPanelError("pricing population missing")

    models: set[tuple[str, str, str]] = set()
    for raw in raw_models:
        if not isinstance(raw, Mapping):
            raise SnapshotPanelError("invalid model row")
        provider = str(raw.get("provider", "")).strip()
        model_id = str(raw.get("model_id", "")).strip()
        version = str(raw.get("model_version", "")).strip()
        if provider != "openai" or not _DATE.fullmatch(version):
            raise SnapshotPanelError("model identity must be exact OpenAI dated snapshot")
        if not model_id.endswith("-" + version):
            raise SnapshotPanelError("model_id must carry the frozen snapshot date")
        identity = (provider, model_id, version)
        if identity in models:
            raise SnapshotPanelError("duplicate model identity")
        models.add(identity)

    actions: dict[str, Mapping[str, object]] = {}
    agent_versions: set[str] = set()
    action_models: set[tuple[str, str, str]] = set()
    for raw in raw_actions:
        if not isinstance(raw, Mapping):
            raise SnapshotPanelError("invalid action row")
        action_id = str(raw.get("action_id", "")).strip()
        if action_id in actions:
            raise SnapshotPanelError("duplicate action_id")
        actions[action_id] = raw
        if str(raw.get("harbor_agent", "")).strip() != "codex":
            raise SnapshotPanelError("all actions must use the same Codex agent")
        agent_version = str(raw.get("agent_version", "")).strip()
        if _SEMVER.fullmatch(agent_version) is None:
            raise SnapshotPanelError("Codex agent version must be exact semver")
        if str(raw.get("harbor_agent_argument", "")).strip() != f"codex@{agent_version}":
            raise SnapshotPanelError("Harbor agent argument lost exact Codex version")
        agent_versions.add(agent_version)
        provider = str(raw.get("provider", "")).strip()
        model_id = str(raw.get("model_id", "")).strip()
        version = str(raw.get("model_version", "")).strip()
        if str(raw.get("harbor_model_argument", "")).strip() != f"{provider}/{model_id}":
            raise SnapshotPanelError("Harbor model argument lost exact provider/model identity")
        action_models.add((provider, model_id, version))

    if set(actions) != set(EXPECTED):
        raise SnapshotPanelError("action population must be exactly DEEP and STANDARD")
    if len(agent_versions) != 1:
        raise SnapshotPanelError("all actions must share one exact Codex version")
    for action_id, expected in EXPECTED.items():
        row = actions[action_id]
        observed = (str(row.get("model_id", "")), str(row.get("model_version", "")))
        if observed != expected:
            raise SnapshotPanelError(f"{action_id} model snapshot differs from frozen V1 panel")
    if action_models != models:
        raise SnapshotPanelError("action/model populations differ")

    interpretation = pricing_doc.get("interpretation")
    if not isinstance(interpretation, Mapping):
        raise SnapshotPanelError("pricing interpretation missing")
    if interpretation.get("regional_processing_uplift_included") is not False:
        raise SnapshotPanelError("V1 panel requires non-regional standard pricing")
    prices: dict[tuple[str, str, str], dict[str, float]] = {}
    for raw in raw_prices:
        if not isinstance(raw, Mapping):
            raise SnapshotPanelError("invalid pricing row")
        identity = (
            str(raw.get("provider", "")).strip(),
            str(raw.get("model_id", "")).strip(),
            str(raw.get("model_version", "")).strip(),
        )
        if identity in prices:
            raise SnapshotPanelError("duplicate pricing identity")
        if str(raw.get("currency", "")).strip() != "USD":
            raise SnapshotPanelError("pricing currency must be USD")
        source = str(raw.get("source_uri", "")).strip()
        if not source.startswith("https://developers.openai.com/"):
            raise SnapshotPanelError("pricing source must be official OpenAI documentation")
        values = {
            name: _finite_positive(name, raw.get(name))
            for name in (
                "input_per_million",
                "cached_input_per_million",
                "cache_write_per_million",
                "long_cache_write_per_million",
                "output_per_million",
            )
        }
        if values["cached_input_per_million"] > values["input_per_million"]:
            raise SnapshotPanelError("cached input price cannot exceed ordinary input price")
        prices[identity] = values
    if set(prices) != models:
        raise SnapshotPanelError("pricing/model populations differ")

    deep = prices[("openai", *EXPECTED["DEEP"])]
    standard = prices[("openai", *EXPECTED["STANDARD"])]
    for field in ("input_per_million", "cached_input_per_million", "output_per_million"):
        if not deep[field] > standard[field]:
            raise SnapshotPanelError("DEEP tier must be strictly more expensive than STANDARD")

    payload = {
        "panel_id": PANEL_ID,
        "agent": "codex",
        "agent_version": next(iter(agent_versions)),
        "action_ids": tuple(sorted(actions)),
        "model_ids": tuple(sorted(row[1] for row in models)),
        "model_manifest_sha256": sha256_file(Path(model_manifest_path)),
        "action_catalog_sha256": sha256_file(Path(action_catalog_path)),
        "pricing_snapshot_sha256": sha256_file(Path(pricing_snapshot_path)),
        "executable_evidence_observed": False,
        "product_promotion_authorized": False,
    }
    return SnapshotPanelAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )
