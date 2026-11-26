"""Inventory tracked CWC materials and enforce the documentation acceptance boundary."""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = "docs/assurance/REQUIREMENTS.json"
STANDARDS = "docs/assurance/STANDARDS.json"
FINDINGS = "docs/assurance/FINDINGS.json"
ROSTER_COMMIT = "87efe1bad7eb062cf415425334adb0e72250ab30"
REQUIRED_COUNTS = (16, 14, 19, 20, 20, 22, 15, 25, 15, 17, 19, 18, 15, 19, 8)
STATUSES = frozenset({"VERIFIED", "INCOMPLETE", "MISSING", "INVALID", "OUTDATED", "NOT_APPLICABLE"})
OBJECT_ID = re.compile(r"[0-9a-f]{40}")
MARKDOWN_LINK = re.compile(r"\]\(([^\s()]+)(?:\s+[^)]*)?\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
DOCUMENT_SUFFIXES = frozenset({".md", ".rst", ".tex", ".bib", ".pdf", ".cff"})
UPSTREAM_LAYOUT = "92d63d4e8bb4df75c3b71618f31ddde2378b2bcd"
UPSTREAM_README = "docs/upstream/NANOCHAT_README.md"
SCOPE_POINTER = "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json"


class AuditError(ValueError):
    """Crosswalk or snapshot is malformed."""


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise AuditError(detail)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def parse(raw: bytes) -> Any:
    return json.loads(raw, object_pairs_hook=unique_object)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def read_commit_json(root: Path, commit: str, path: str) -> Any:
    return parse(git(root, "show", f"{commit}:{path}"))


def inventory(root: Path, commit: str) -> dict[str, dict[str, Any]]:
    records = {}
    for entry in git(root, "ls-tree", "-rlz", commit).split(b"\0"):
        if not entry:
            continue
        metadata, pathname = entry.split(b"\t", 1)
        mode, kind, oid, size = metadata.decode("ascii").split()
        path = pathname.decode("utf-8")
        require(kind == "blob" and OBJECT_ID.fullmatch(oid) is not None, f"unknown tree entry: {path}")
        require(path not in records, f"duplicate tracked path: {path}")
        rel = Path(path)
        if path.startswith(("artifacts/", "runs/")):
            classification = "evidence"
        elif path.startswith(("docs/", "research/", "HANDOFF/")) or rel.suffix in DOCUMENT_SUFFIXES:
            classification = "documentation"
        elif path.startswith(("tests/", ".github/workflows/", "schemas/", "engineering/")):
            classification = "verification_support"
        else:
            classification = "source_or_configuration"
        records[path] = {
            "blob_oid": oid, "mode": mode, "bytes": int(size), "kind": classification,
            "status": "INCOMPLETE", "basis": "tracked byte identity; substantive review pending",
        }
    return records


def obligation_roster(register: dict[str, Any]) -> tuple[tuple[int, str], ...]:
    return tuple((category["category"], item)
                 for category in register["categories"]
                 for profile in category["profiles"]
                 for item in profile["items"])


def bind_rosters(root: Path, register: dict[str, Any], standards: list[dict[str, Any]]) -> None:
    frozen = read_commit_json(root, ROSTER_COMMIT, REQUIREMENTS)
    require(obligation_roster(register) == obligation_roster(frozen), "frozen obligation identity drift")
    approved = read_commit_json(root, ROSTER_COMMIT, STANDARDS)["sources"]
    expected = [(row["id"], None if row["authority"] == "target unresolved" else row["url"]) for row in approved]
    require([(row["id"], row["url"]) for row in standards] == expected, "frozen source URI drift")


def relative_link_findings(path: str, text: str, paths: set[str]) -> list[dict[str, Any]]:
    result = []
    fence = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = FENCE.match(line)
        if match:
            marker = match[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        for link in MARKDOWN_LINK.findall(line):
            target = link.partition("#")[0].partition("?")[0]
            if not target or ":" in target or target.startswith(("/", "<")):
                continue
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            if relative not in paths:
                result.append({"line": line_number, "target": target})
    return result


def inspect_relative_links(root: Path, commit: str, records: dict[str, Any]) -> dict[str, Any]:
    paths = set(records) | {str(parent) for path in records for parent in Path(path).parents}
    upstream = inventory(root, UPSTREAM_LAYOUT)
    require(records[UPSTREAM_README]["blob_oid"] == upstream["README.md"]["blob_oid"],
            "upstream documentation bytes differ from the pinned original")
    upstream_paths = set(upstream) | {str(parent) for path in upstream for parent in Path(path).parents}
    findings = {}
    checked = 0
    for path in records:
        if not path.endswith(".md"):
            continue
        raw = git(root, "show", f"{commit}:{path}")
        checked += 1
        try:
            if path == UPSTREAM_README:
                errors = relative_link_findings("README.md", raw.decode("utf-8"), upstream_paths)
            else:
                errors = relative_link_findings(path, raw.decode("utf-8"), paths)
        except UnicodeDecodeError:
            errors = [{"line": 0, "target": "non-UTF-8 Markdown"}]
        if errors:
            findings[path] = errors
    return {"files_scanned": checked, "findings": findings,
            "scope": "simple inline repo-relative Markdown paths; excludes fragments, external links and fenced examples"}


def validate_requirements(
    register: dict[str, Any], records: dict[str, Any], production_disabled: bool,
) -> list[dict[str, Any]]:
    require(register.get("schema") == "cwc-documentation-requirements-v1", "requirement schema")
    categories = register["categories"]
    require([row["category"] for row in categories] == list(range(1, 16)), "category roster")
    rows = []
    seen = set()
    for category, expected in zip(categories, REQUIRED_COUNTS, strict=True):
        number = category["category"]
        index = 0
        for profile in category["profiles"]:
            status = profile["status"]
            require(status in STATUSES, "unknown requirement status")
            require(status != "VERIFIED", "independent issuer admission has no approved policy")
            reason = profile["finding"]
            require(isinstance(reason, str) and bool(reason.strip()), "missing classification rationale")
            paths = profile["evidence"]
            require(bool(paths) and len(set(paths)) == len(paths), "empty or duplicate evidence roster")
            require(all(path in records for path in paths), f"unbound evidence in category {number}: {paths}")
            for item in profile["items"]:
                require(isinstance(item, str) and bool(item.strip()) and item not in seen, "invalid/duplicate obligation")
                seen.add(item)
                index += 1
                if status == "NOT_APPLICABLE":
                    require(number == 8 and item == "Act of operational commissioning" and production_disabled,
                            "unsupported scope exclusion")
                rows.append({
                    "id": f"C{number:02d}-{index:02d}", "category": number,
                    "item": item, "status": status,
                    "applicability": "excluded within audited scope" if status == "NOT_APPLICABLE" else "in scope or pending",
                    "finding": reason, "evidence": {path: records[path]["blob_oid"] for path in paths},
                })
        require(index == expected, f"category {number} has {index} obligations; expected {expected}")
    return rows


def validate_standards(register: dict[str, Any]) -> list[dict[str, Any]]:
    require(register.get("schema") == "cwc-standards-crosswalk-v1", "standards schema")
    rows = register["sources"]
    require([row["id"] for row in rows] == [f"S-{i:02d}" for i in range(1, 32)], "standards roster")
    for row in rows:
        require(row["status"] in {"INCOMPLETE", "NOT_APPLICABLE"}, "unsupported standards disposition")
        url = row["url"]
        if row["authority"] == "target unresolved":
            require(url is None, "unresolved authority cannot supply an official URI")
        else:
            require(isinstance(url, str) and url.startswith("https://"), "unbound official source")
        require(bool(row["finding"].strip()), "empty source assessment")
        require(bool(row["categories"]) and set(row["categories"]) <= set(range(1, 16)), "unsupported category")
        require((row["status"] == "NOT_APPLICABLE") == (row["authority"] == "scope excluded"),
                "unjustified external-standard exclusion")
    return rows


def audit(root: Path = ROOT) -> dict[str, Any]:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    tree = git(root, "rev-parse", f"{head}^{{tree}}").decode().strip()
    require(not git(root, "status", "--porcelain", "--untracked-files=no").strip(), "tracked checkout must be clean")
    records = inventory(root, head)
    reg = read_commit_json(root, head, REQUIREMENTS)
    baseline = reg["audit_baseline"]
    require(OBJECT_ID.fullmatch(baseline["commit"]) is not None and
            git(root, "rev-parse", f'{baseline["commit"]}^{{tree}}').decode().strip() == baseline["tree"],
            "audit baseline tree mismatch")
    git(root, "merge-base", "--is-ancestor", baseline["commit"], head)
    pointer = read_commit_json(root, head, SCOPE_POINTER)
    disabled = pointer.get("production_control_authorized") is False and pointer.get("activation_authorized") is False
    requirements = validate_requirements(reg, records, disabled)
    standards = validate_standards(read_commit_json(root, head, STANDARDS))
    bind_rosters(root, reg, standards)
    findings = read_commit_json(root, head, FINDINGS)
    require(findings.get("schema") == "cwc-documentation-findings-v1", "findings schema")
    require(findings.get("baseline") == baseline["commit"], "findings baseline")
    previous = read_commit_json(root, ROSTER_COMMIT, FINDINGS)["findings"]
    reported = {row["id"]: row for row in findings["findings"]}
    for old in previous:
        current = reported.get(old["id"])
        require(current is not None and
                {k: v for k, v in current.items() if k != "disposition"} ==
                {k: v for k, v in old.items() if k != "disposition"}, "finding roster or evidence drift")
    base_records = inventory(root, baseline["commit"])
    ids = set()
    for row in findings["findings"]:
        path, disposition = row["path"], row["disposition"]
        require(row["id"] not in ids and path in base_records and path in records, "unbound finding")
        ids.add(row["id"])
        require(row["status"] in {"INVALID", "OUTDATED", "INCOMPLETE"}, "unexpected finding status")
        require(disposition in {"CORRECTION_PENDING_REVIEW", "OPEN"}, "invalid finding disposition")
        require(base_records[path]["blob_oid"] == row["baseline_blob_oid"], f"finding baseline mismatch: {path}")
        if disposition == "CORRECTION_PENDING_REVIEW":
            require(records[path]["blob_oid"] != row["baseline_blob_oid"], f"candidate change absent: {path}")
        else:
            records[path]["status"] = row["status"]
            records[path]["basis"] = row["finding"]
    blockers = [row["id"] for row in (*requirements, *standards)
                if row["status"] not in {"VERIFIED", "NOT_APPLICABLE"}]
    blockers.extend(row["id"] for row in findings["findings"])
    links = inspect_relative_links(root, head, records)
    blockers.extend(f"LINK:{path}" for path in links["findings"])
    return {
        "schema": "cwc-documentation-audit-v1", "commit": head, "tree": tree, "baseline": baseline,
        "acceptance": "BLOCKED" if blockers else "ACCEPTED", "blockers": blockers,
        "inventory": records, "requirements": requirements, "standards": standards, "findings": findings["findings"],
        "relative_links": links,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a new report outside the checkout")
    parser.add_argument("--accept", action="store_true", help="Fail if acceptance is blocked")
    args = parser.parse_args()
    try:
        report = audit()
        if args.output is not None:
            output = args.output.resolve()
            require(not output.is_relative_to(ROOT), "report output must be outside the checkout")
            with output.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
    except (AuditError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"DOCUMENTATION AUDIT INVALID: {exc}")
        return 2
    counts = Counter(row["status"] for row in report["requirements"])
    kinds = Counter(row["kind"] for row in report["inventory"].values())
    print(json.dumps({
        "commit": report["commit"], "tree": report["tree"], "inventory": dict(kinds),
        "requirements": dict(counts), "standards": len(report["standards"]),
        "open_items": len(report["blockers"]), "acceptance": report["acceptance"],
        "markdown_scanned": report["relative_links"]["files_scanned"],
        "markdown_with_link_findings": len(report["relative_links"]["findings"]),
    }, sort_keys=True))
    return 3 if args.accept and report["acceptance"] != "ACCEPTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
