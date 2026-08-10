"""Build and validate a deterministic CycloneDX SBOM from the frozen uv lock."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/security/SBOM.cdx.json")
HASH = re.compile(r"^sha256:([0-9a-f]{64})$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: Path = ROOT) -> dict[str, Any]:
    lock_path = root / "uv.lock"
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages: dict[tuple[str, str], set[str]] = {}
    for package in sorted(lock["package"], key=lambda item: (item["name"], item["version"])):
        name = package["name"]
        version = package["version"]
        hashes = packages.setdefault((name, version), set())
        sources = [package.get("sdist", {}), *package.get("wheels", [])]
        for source in sources:
            match = HASH.fullmatch(source.get("hash", ""))
            if match:
                hashes.add(match.group(1).upper())
    components: list[dict[str, Any]] = []
    for (name, version), hashes in sorted(packages.items()):
        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
        }
        if hashes:
            component["hashes"] = [{"alg": "SHA-256", "content": value} for value in sorted(hashes)]
        components.append(component)
    lock_sha = _sha256(lock_path)
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"cwc:uv.lock:{lock_sha}")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": "pkg:generic/cognitive-wiring-core",
                "name": "Cognitive Wiring Core",
                "version": "1.0.0",
            },
            "properties": [{"name": "cwc:uv-lock-sha256", "value": lock_sha}],
        },
        "components": components,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def validate(root: Path = ROOT, output: Path = DEFAULT_OUTPUT) -> list[str]:
    path = output if output.is_absolute() else root / output
    if not path.is_file():
        return [f"{output}: SBOM missing"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{output}: invalid SBOM: {exc}"]
    expected = build(root)
    errors: list[str] = []
    if actual != expected:
        errors.append(f"{output}: SBOM does not exactly match frozen uv.lock")
    refs = [component.get("bom-ref") for component in actual.get("components", [])]
    if len(refs) != len(set(refs)):
        errors.append(f"{output}: duplicate component bom-ref")
    if not refs:
        errors.append(f"{output}: no dependency components")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        errors = validate(output=args.output)
        if errors:
            for error in errors:
                print(f"SBOM-FAIL: {error}")
            return 1
        print(f"SBOM: PASS ({len(build()['components'])} frozen components)")
        return 0
    path = args.output if args.output.is_absolute() else ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(build()), encoding="utf-8")
    print(f"SBOM: wrote {path} ({len(build()['components'])} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
