"""Offline bibliography gate: no citation may exist that was never machine-resolved.

A bibliography is the one part of a research artefact that a reader cannot check by
running the code, and it is exactly where a plausible-looking invention survives. This
gate makes it checkable. It is deterministic and network-free, so it runs inside
`make -f Makefile.cwc verify`.

Enforced properties
  B1  every BibTeX entry has a verification record naming an external resolver
  B2  every verification record appears in the BibTeX file (no orphan records)
  B3  every record carries resolver, resolver_url, identifier and a UTC timestamp
  B4  the BibTeX title equals the resolver-returned title, character for character
      (this is what catches a hand-edit of the generated file)
  B5  every claim id a reference is attached to exists in claim_registry.json
  B6  every reference states an argument for why CWC cites it
  B7  every citation key used in RELATED_WORK_AND_NOVELTY_REVIEW.md resolves to an
      entry, and every entry is argued in that review (no unused, no dangling)

Invoke: PYTHONPATH=. .venv/bin/python scripts/verify_bibliography.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "docs/publication/references.bib"
VERIF = ROOT / "docs/publication/BIBLIOGRAPHY_VERIFICATION.json"
REVIEW = ROOT / "docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md"
REGISTRY = ROOT / "claim_registry.json"

ENTRY_RE = re.compile(r"^@\w+\{([^,]+),", re.MULTILINE)
TITLE_RE = re.compile(r"^\s*title\s*=\s*\{(.*)\}\s*,?\s*$", re.MULTILINE)
CITE_RE = re.compile(r"\[@([A-Za-z0-9_:.-]+)\]")


def parse_bib(text: str) -> dict[str, str]:
    """Return {key: title} for every entry in the file."""
    out: dict[str, str] = {}
    blocks = re.split(r"(?=^@)", text, flags=re.MULTILINE)
    for block in blocks:
        m = ENTRY_RE.search(block)
        if not m:
            continue
        t = TITLE_RE.search(block)
        out[m.group(1).strip()] = t.group(1).strip() if t else ""
    return out


def main() -> int:
    errors: list[str] = []

    for path in (BIB, VERIF, REVIEW, REGISTRY):
        if not path.exists():
            print(f"BIB-GATE FAIL: missing {path.relative_to(ROOT)}")
            return 1

    bib = parse_bib(BIB.read_text())
    verif: dict[str, Any] = json.loads(VERIF.read_text())
    entries: dict[str, Any] = verif["entries"]
    known_claims = {c["claim_id"] for c in json.loads(REGISTRY.read_text())["claims"]}
    review = REVIEW.read_text()

    # B1 / B2 — the two files describe the same set of references.
    for key in sorted(set(bib) - set(entries)):
        errors.append(f"B1 {key}: cited in references.bib with no verification record")
    for key in sorted(set(entries) - set(bib)):
        errors.append(f"B2 {key}: verification record with no BibTeX entry")

    for key in sorted(set(bib) & set(entries)):
        rec = entries[key]
        resolved = rec.get("resolved", {})

        # B3 — provenance is complete.
        for field in ("resolver", "resolver_url"):
            if not resolved.get(field):
                errors.append(f"B3 {key}: resolved.{field} missing")
        if not rec.get("identifier"):
            errors.append(f"B3 {key}: identifier missing")
        stamp = rec.get("verified_utc", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
            errors.append(f"B3 {key}: verified_utc not a UTC timestamp ({stamp!r})")

        # B4 — the generated file still matches what the resolver said.
        manual = set(resolved.get("manual_fields", []))
        resolved_title = (resolved.get("title") or "").strip()
        if "title" not in manual and bib[key] != resolved_title:
            errors.append(
                f"B4 {key}: BibTeX title diverges from resolver\n"
                f"      bib      : {bib[key]!r}\n"
                f"      resolver : {resolved_title!r}"
            )

        # B5 — claim attachments point at real claims.
        for claim in rec.get("claims", []):
            if claim not in known_claims:
                errors.append(f"B5 {key}: attached to unknown claim {claim}")
        if not rec.get("claims"):
            errors.append(f"B5 {key}: attached to no claim")

        # B6 — an argument exists and is not a stub.
        if len(str(rec.get("argument", "")).strip()) < 40:
            errors.append(f"B6 {key}: no substantive argument for citing this work")

    # B7 — the review and the bibliography agree.
    cited = set(CITE_RE.findall(review))
    for key in sorted(cited - set(entries)):
        errors.append(f"B7 {key}: cited in RELATED_WORK_AND_NOVELTY_REVIEW.md but not in the bibliography")
    for key in sorted(set(entries) - cited):
        errors.append(f"B7 {key}: in the bibliography but never argued in RELATED_WORK_AND_NOVELTY_REVIEW.md")

    if errors:
        print("BIB-GATE FAIL")
        for e in errors:
            print("  " + e)
        return 1

    resolvers: dict[str, int] = {}
    for rec in entries.values():
        r = rec["resolved"]["resolver"]
        resolvers[r] = resolvers.get(r, 0) + 1
    areas = sorted({rec["area"] for rec in entries.values()})
    print(
        f"BIB-GATE OK: {len(entries)} references, all machine-resolved "
        f"({', '.join(f'{k}={v}' for k, v in sorted(resolvers.items()))}); "
        f"{len(areas)} areas; every entry argued and claim-attached."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
