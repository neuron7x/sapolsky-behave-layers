from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import documentation_audit as audit


class DocumentationAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.register = json.loads((audit.ROOT / audit.REQUIREMENTS).read_text(encoding="utf-8"))
        self.records = {
            path: {"blob_oid": "a" * 40}
            for category in self.register["categories"]
            for profile in category["profiles"]
            for path in profile["evidence"]
        }

    def test_required_roster_expands_to_individual_entries(self) -> None:
        rows = audit.validate_requirements(self.register, self.records, True)
        self.assertEqual(len(rows), 262)
        self.assertEqual(len({row["id"] for row in rows}), 262)
        self.assertEqual(sum(row["status"] == "NOT_APPLICABLE" for row in rows), 1)

    def test_missing_obligation_is_rejected(self) -> None:
        self.register["categories"][0]["profiles"][0]["items"].pop()
        with self.assertRaisesRegex(audit.AuditError, "expected"):
            audit.validate_requirements(self.register, self.records, True)

    def test_duplicate_obligation_is_rejected(self) -> None:
        items = self.register["categories"][0]["profiles"][0]["items"]
        items[-1] = items[0]
        with self.assertRaisesRegex(audit.AuditError, "duplicate obligation"):
            audit.validate_requirements(self.register, self.records, True)

    def test_unsupported_verified_mark_is_rejected(self) -> None:
        self.register["categories"][0]["profiles"][0]["status"] = "VERIFIED"
        with self.assertRaisesRegex(audit.AuditError, "issuer admission"):
            audit.validate_requirements(self.register, self.records, True)

    def test_in_scope_exclusion_is_rejected(self) -> None:
        self.register["categories"][0]["profiles"][0]["status"] = "NOT_APPLICABLE"
        with self.assertRaisesRegex(audit.AuditError, "unsupported scope exclusion"):
            audit.validate_requirements(self.register, self.records, True)

    def test_commissioning_exclusion_expires_with_authority(self) -> None:
        with self.assertRaisesRegex(audit.AuditError, "unsupported scope exclusion"):
            audit.validate_requirements(self.register, self.records, False)

    def test_missing_evidence_is_rejected(self) -> None:
        self.records.pop("CWC_CLOSURE.md")
        with self.assertRaisesRegex(audit.AuditError, "unbound evidence"):
            audit.validate_requirements(self.register, self.records, True)

    def test_conflicting_json_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(audit.AuditError, "duplicate JSON field"):
            audit.parse(b'{"scope": "approved", "scope": "absent"}')

    def test_missing_external_requirement_is_rejected(self) -> None:
        standards = json.loads((audit.ROOT / audit.STANDARDS).read_text(encoding="utf-8"))
        standards["sources"].pop()
        with self.assertRaisesRegex(audit.AuditError, "standards roster"):
            audit.validate_standards(standards)

    def test_same_size_substitution_is_rejected_by_frozen_roster(self) -> None:
        self.register["categories"][0]["profiles"][0]["items"][0] = "Unrelated replacement"
        standards = audit.validate_standards(
            json.loads((audit.ROOT / audit.STANDARDS).read_text(encoding="utf-8"))
        )
        with self.assertRaisesRegex(audit.AuditError, "frozen obligation identity drift"):
            audit.bind_rosters(audit.ROOT, self.register, standards)

    def test_unbound_official_uri_is_rejected(self) -> None:
        standards = json.loads((audit.ROOT / audit.STANDARDS).read_text(encoding="utf-8"))["sources"]
        standards[0]["url"] = "https://example.invalid/"
        with self.assertRaisesRegex(audit.AuditError, "frozen source URI drift"):
            audit.bind_rosters(audit.ROOT, self.register, standards)

    def test_relative_path_policy_detects_absence_and_skips_fences(self) -> None:
        text = "[good](../README.md)\n[missing](missing.md)\n```\n[fake](fenced.md)\n```\n"
        self.assertEqual(audit.relative_link_findings("docs/a.md", text, {"README.md"}),
                         [{"line": 2, "target": "missing.md"}])

    def test_source_binding_excludes_dirty_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit.git(root, "init", "-q")
            path = root / "document.md"
            path.write_text("first\n", encoding="utf-8")
            audit.git(root, "add", "document.md")
            audit.git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                      "commit", "-qm", "fixture")
            first = audit.inventory(root, "HEAD")["document.md"]
            path.write_text("dirty\n", encoding="utf-8")
            self.assertEqual(audit.inventory(root, "HEAD")["document.md"], first)
            with self.assertRaisesRegex(audit.AuditError, "tracked checkout must be clean"):
                audit.audit(root)


if __name__ == "__main__":
    unittest.main()
