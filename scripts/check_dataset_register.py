"""Check the synthetic dataset catalogue against its declared supported schema fields."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DatasetLoader(yaml.SafeLoader):
    """Safe YAML loader with unambiguous mappings."""


def unique_mapping(loader: DatasetLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key, value in loader.construct_pairs(node, deep=True):
        if key in result:
            raise ValueError(f"duplicate YAML field: {key}")
        result[key] = value
    return result


DatasetLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml(text: str) -> dict:
    return yaml.load(text, Loader=DatasetLoader)


def validate(payload: dict, schema: dict, root: Path) -> None:
    root_fields = set(schema["properties"])
    if set(payload) != root_fields:
        raise ValueError("unexpected dataset-register root fields")
    collection = schema["properties"]["datasets"]
    rows = payload["datasets"]
    if type(rows) is not list or len(rows) < collection["minItems"]:
        raise ValueError("dataset roster is empty or malformed")
    item_schema = collection["items"]
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not set(item_schema["required"]) <= set(row) <= set(item_schema["properties"]):
            raise ValueError("invalid dataset fields")
        for key, value in row.items():
            rules = item_schema["properties"][key]
            if "const" in rules and value != rules["const"]:
                raise ValueError(f"invalid dataset field {key}")
            if rules.get("type") == "string":
                if not isinstance(value, str) or not value.strip() or (
                    "pattern" in rules and not re.search(rules["pattern"], value)
                ):
                    raise ValueError(f"invalid dataset field {key}")
            if rules.get("type") == "array":
                if type(value) is not list or len(value) < rules.get("minItems", 0) or (
                    not all(isinstance(entry, str) and entry.strip() for entry in value)
                ):
                    raise ValueError(f"invalid dataset array {key}")
                if rules.get("uniqueItems") and len(set(value)) != len(value):
                    raise ValueError(f"duplicate dataset entries in {key}")
        if row["dataset_id"] in seen:
            raise ValueError("duplicate dataset identity")
        seen.add(row["dataset_id"])
        path = (root / row["generator"]).resolve()
        if not path.is_relative_to(root / "experiments") or not path.exists():
            raise ValueError(f"unbound generator: {row['generator']}")


def main() -> int:
    try:
        schema = json.loads((ROOT / "schemas/dataset.schema.json").read_text(encoding="utf-8"))
        payload = load_yaml((ROOT / "docs/data/DATASET_REGISTER.yaml").read_text(encoding="utf-8"))
        validate(payload, schema, ROOT)
    except (OSError, TypeError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"DATASET REGISTER FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"DATASET REGISTER PASS: {len(payload['datasets'])} synthetic generator records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
