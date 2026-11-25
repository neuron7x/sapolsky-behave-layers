"""Bounded synthetic custody attacks; no model outputs or scientific evidence."""
from copy import deepcopy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from experiments.cwc_collision import audit as collision
from experiments.cwc_source_admission import acquisition
from experiments.cwc_source_admission import collision_delta
from experiments.cwc_source_admission import custody
from experiments.cwc_source_admission import verify_receipt
from experiments.real_transfer_01 import source_intake


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name) / "sources"
        self.payloads = {
            "averitec_dev.json": b'{"synthetic":"source-one"}\n',
            "hybridqa_dev.json": b'{"synthetic":"source-two"}\n',
            "wikitable_links.zip": b"synthetic-archive-byte-identity\n",
        }
        pins = {
            name: {
                "byte_length": len(raw),
                "sha256": digest(raw),
                "git_blob": None if name.endswith(".zip") else source_intake.git_blob(raw),
            }
            for name, raw in self.payloads.items()
        }
        pin_patch = patch.object(acquisition, "PINS", pins)
        pin_patch.start()
        self.addCleanup(pin_patch.stop)
        self.downloaded = []

        def download(url, path, limit):
            raw = self.payloads[path.name]
            self.assertLessEqual(len(raw), limit)
            path.write_bytes(raw)
            self.downloaded.append(url)

        transport_patch = patch.object(acquisition, "_download", side_effect=download)
        transport_patch.start()
        self.addCleanup(transport_patch.stop)

    def test_actual_bytes_roundtrip_and_nonpromotion(self):
        receipt = acquisition.acquire(self.cache)
        self.assertEqual(acquisition.validate_receipt(self.cache, receipt), receipt)
        self.assertEqual(self.downloaded, [source[3] for source in source_intake.SOURCES])
        self.assertEqual(receipt["observation_kind"], "SELF_OBSERVED_NOT_AUTHENTICATED")
        for item in receipt["sources"]:
            raw = self.payloads[item["name"]]
            self.assertEqual(item["byte_length"], len(raw))
            self.assertEqual(item["sha256"], digest(raw))
        for key, value in source_intake.AUTHORITY.items():
            self.assertEqual(receipt[key], value)

    def test_receipt_substitution_and_time_confusion_rejected(self):
        receipt = acquisition.acquire(self.cache)
        mutations = []
        for key, value in (
            ("byte_length", True),
            ("sha256", "0" * 64),
            ("git_blob", "0" * 40),
            ("canonical_url", "https://example.org/replacement.json"),
            ("ref", "0" * 40),
            ("name", "replacement.json"),
            ("started_at", "2099-01-01T00:00:00.000000Z"),
        ):
            changed = deepcopy(receipt)
            changed["sources"][0][key] = value
            mutations.append((key, changed))
        changed = deepcopy(receipt)
        changed["sources"].append(deepcopy(changed["sources"][0]))
        mutations.append(("duplicate-source", changed))
        changed = deepcopy(receipt)
        changed["sources"].pop()
        mutations.append(("missing-source", changed))
        changed = deepcopy(receipt)
        changed["sources"][0]["unexpected"] = "field"
        mutations.append(("extra-source-field", changed))
        changed = deepcopy(receipt)
        changed["scientific_promotion_authorized"] = True
        mutations.append(("forged-authority", changed))
        changed = deepcopy(receipt)
        changed["started_at"] = "2099-01-01T00:00:00.000000Z"
        mutations.append(("future-root-time", changed))
        changed = deepcopy(receipt)
        changed["completed_at"] = "1970-01-01T00:00:00.000000Z"
        mutations.append(("reversed-root-time", changed))
        for name, changed in mutations:
            with self.subTest(mutation=name):
                with self.assertRaises(acquisition.AcquisitionError):
                    acquisition.validate_receipt(self.cache, changed)

    def test_changed_bytes_extra_files_and_symlinks_rejected(self):
        receipt = acquisition.acquire(self.cache)
        first = self.cache / "averitec_dev.json"
        first.write_bytes(b"substituted-source")
        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.validate_receipt(self.cache, receipt)
        first.write_bytes(self.payloads[first.name])
        extra = self.cache / "undeclared.json"
        extra.write_bytes(b"undeclared")
        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.validate_receipt(self.cache, receipt)
        extra.unlink()
        backing = self.cache.parent / "backing.json"
        first.replace(backing)
        first.symlink_to(backing)
        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.validate_receipt(self.cache, receipt)
        first.unlink()
        os.mkfifo(first)
        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.validate_receipt(self.cache, receipt)

    def test_existing_cache_and_unsafe_acquisition_urls_rejected(self):
        self.cache.mkdir()
        with self.assertRaises(acquisition.AcquisitionError):
            acquisition.acquire(self.cache)
        self.assertEqual(self.downloaded, [])
        for value in (
            "http://example.org/source",
            "file:///tmp/source",
            "https://user:password@example.org/source",
            "https://example.org/source#fragment",
            "https:///source",
            "https://example.org:invalid/source",
        ):
            with self.subTest(url=value):
                with self.assertRaises(acquisition.AcquisitionError):
                    acquisition._require_https(value)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.key = "synthetic-table"
        self.table = {
            "uid": self.key,
            "url": "https://en.wikipedia.org/wiki/Synthetic_Table",
            "header": [["PRIVATE_HEADER_TEXT", ["/wiki/Alpha"]]],
            "data": [[["PRIVATE_CELL_TEXT", []]]],
        }
        self.docs = {
            "/wiki/Alpha": "PRIVATE_REFERENCED_PASSAGE",
            "/wiki/Unreferenced": "PRIVATE_UNREFERENCED_PASSAGE",
        }
        prefix = source_intake.WIKI_PREFIX
        self.table_meta = {
            "member": f"{prefix}/tables_tok/{self.key}.json",
            "byte_length": 123,
            "sha256": "1" * 64,
        }
        self.request_meta = {
            "member": f"{prefix}/request_tok/{self.key}.json",
            "byte_length": 456,
            "sha256": "2" * 64,
        }

    def inventory(self, table=None, docs=None):
        return custody.table_inventory(
            self.key,
            self.table if table is None else table,
            self.docs if docs is None else docs,
            self.table_meta,
            self.request_meta,
        )

    def test_direct_and_derived_attribution_do_not_claim_verification(self):
        direct = custody.attribution_for_value(
            "https://en.wikipedia.org/w/index.php?title=Example&oldid=123456", "table.url"
        )
        self.assertEqual(direct["url_origin"], "SOURCE_ABSOLUTE_URL")
        self.assertTrue(direct["structural_url_valid"])
        self.assertEqual(str(direct["historical_revision_id"]), "123456")
        derived = custody.attribution_for_value("/wiki/Example", "request_tok.key")
        self.assertEqual(derived["url"], "https://en.wikipedia.org/wiki/Example")
        self.assertEqual(derived["url_origin"], "MECHANICALLY_DERIVED_WIKIPEDIA_PATH")
        self.assertIsNone(derived["historical_revision_id"])
        for result in (direct, derived):
            for field in ("http_fetch_performed", "provenance_verified", "imported_notices_reviewed"):
                self.assertIs(result[field], False)

    def test_invalid_or_ambiguous_attribution_remains_unresolved(self):
        for value in (
            "javascript:alert(1)",
            "file:///etc/passwd",
            "https://user:password@example.org/article",
            "https:///missing-host",
            "https://example.org:invalid/article",
            "/other/Example",
            "//evil.example/wiki/Example",
            "/wiki/",
            "free text is not an article identity",
            "https://example.org/line\nbreak",
            None,
            True,
        ):
            with self.subTest(value=value):
                result = custody.attribution_for_value(value, "request_tok.key")
                self.assertEqual(result["url_origin"], "UNRESOLVED")
                self.assertIs(result["structural_url_valid"], False)
                self.assertIs(result["provenance_verified"], False)
                self.assertIsNone(result["url"])

    def test_full_request_dictionary_includes_unreferenced_payload(self):
        result = self.inventory()
        self.assertEqual(result["passage_count"], 2)
        self.assertEqual(result["table_cell_link_count"], 1)
        self.assertEqual(result["unreferenced_passage_count"], 1)
        by_hash = {row["key_sha256"]: row for row in result["passages"]}
        self.assertEqual(set(by_hash), {digest(key.encode()) for key in self.docs})
        for key, passage in self.docs.items():
            row = by_hash[digest(key.encode())]
            self.assertEqual(row["passage_sha256"], digest(passage.encode()))
            self.assertEqual(row["passage_byte_length"], len(passage.encode()))
        self.assertEqual(result["table_member"], self.table_meta)
        self.assertEqual(result["request_member"], self.request_meta)

    def test_metadata_excludes_raw_table_and_passage_content(self):
        result = self.inventory()
        encoded = json.dumps(result, sort_keys=True)
        for private in (
            "PRIVATE_HEADER_TEXT", "PRIVATE_CELL_TEXT", *self.docs.values()
        ):
            self.assertNotIn(private, encoded)
        self.assertEqual(result["table_id_sha256"], digest(self.key.encode()))
        changed_docs = dict(self.docs)
        changed_docs["/wiki/Unreferenced"] = "CHANGED_UNREFERENCED_PASSAGE"
        changed = self.inventory(docs=changed_docs)
        self.assertNotEqual(result["passages"], changed["passages"])

    def test_malformed_payloads_and_unbound_member_metadata_rejected(self):
        for changed in ({"/wiki/Alpha": True}, {"/wiki/Unreferenced": "only unlinked"}):
            with self.subTest(docs=changed):
                with self.assertRaises(ValueError):
                    self.inventory(docs=changed)
        changed = deepcopy(self.table)
        changed["uid"] = "another-table"
        with self.assertRaises(ValueError):
            self.inventory(table=changed)
        for field, value in (("member", "unbound.json"), ("byte_length", True),
                             ("sha256", "invalid-digest")):
            with self.subTest(field=field):
                changed_meta = deepcopy(self.request_meta)
                changed_meta[field] = value
                with self.assertRaises(ValueError):
                    custody.table_inventory(self.key, self.table, self.docs,
                                            self.table_meta, changed_meta)

    def test_exact_ordered_cohort_join_rejects_membership_substitution(self):
        hashes = sorted(digest(value.encode()) for value in ("one", "two", "three", "four"))
        records = {identity: {"synthetic_id": i} for i, identity in enumerate(hashes)}
        counts = {"CALIBRATION": 1, "PRIMARY": 2, "REPLICATION": 1}
        groups = {
            "CALIBRATION": hashes[:1], "PRIMARY": hashes[1:3], "REPLICATION": hashes[3:]
        }
        cohorts = {
            name: {"count": len(ids), "record_hashes": ids,
                   "cohort_sha256": digest("\n".join(ids).encode())}
            for name, ids in groups.items()
        }
        joined = custody.join_cohort_records(records, cohorts, expected_counts=counts)
        self.assertEqual([row["record_hash"] for row in joined], hashes)
        self.assertEqual([row["cohort"] for row in joined],
                         ["CALIBRATION", "PRIMARY", "PRIMARY", "REPLICATION"])
        mutations = []
        reverse = deepcopy(cohorts)
        reverse["PRIMARY"]["record_hashes"].reverse()
        reverse["PRIMARY"]["cohort_sha256"] = digest(
            "\n".join(reverse["PRIMARY"]["record_hashes"]).encode()
        )
        mutations.append(reverse)
        boolean = deepcopy(cohorts)
        boolean["CALIBRATION"]["count"] = True
        mutations.append(boolean)
        overlap = deepcopy(cohorts)
        overlap["REPLICATION"]["record_hashes"] = hashes[:1]
        overlap["REPLICATION"]["cohort_sha256"] = digest(hashes[0].encode())
        mutations.append(overlap)
        bad_digest = deepcopy(cohorts)
        bad_digest["PRIMARY"]["cohort_sha256"] = "0" * 64
        mutations.append(bad_digest)
        for i, changed in enumerate(mutations):
            with self.subTest(mutation=i):
                with self.assertRaises(ValueError):
                    custody.join_cohort_records(records, changed, expected_counts=counts)
        missing = dict(records)
        missing.pop(hashes[0])
        with self.assertRaises(ValueError):
            custody.join_cohort_records(missing, cohorts, expected_counts=counts)


class IndependentVerifierTests(unittest.TestCase):
    def test_unresolved_reason_binds_the_actual_failure_stage(self):
        missing = "MISSING_OR_MALFORMED_SOURCE_URL"
        invalid = "INVALID_OR_AMBIGUOUS_SOURCE_URL"
        for value, reason in ((None, missing), ("line\nbreak", missing),
                              ("not-an-absolute-url", invalid),
                              ("https://example.org:invalid/article", invalid)):
            with self.subTest(value=value):
                item = custody.attribution_for_value(value, "source_url")
                self.assertEqual(item["unresolved_reason"], reason)
                verified = []
                verify_receipt.verify_url(item, value, "source_url", verified)
                self.assertEqual(verified, [item])
                for substituted in ("SYNTHETIC_UNBOUND_TEXT", invalid if reason == missing else missing):
                    changed = {**item, "unresolved_reason": substituted}
                    observed = []
                    with self.assertRaisesRegex(verify_receipt.VerificationError, "UNRESOLVED_REASON"):
                        verify_receipt.verify_url(changed, value, "source_url", observed)
                    self.assertEqual(observed, [])

    def test_resolved_url_rejects_an_unresolved_reason_field(self):
        for value in ("https://example.org/article", "http://example.org/article", "/wiki/Example"):
            with self.subTest(value=value):
                item = custody.attribution_for_value(value, "source_url")
                verify_receipt.verify_url(item, value, "source_url", [])
                for reason in ("SYNTHETIC_UNBOUND_TEXT", "MISSING_OR_MALFORMED_SOURCE_URL"):
                    changed = {**item, "unresolved_reason": reason}
                    observed = []
                    with self.assertRaisesRegex(verify_receipt.VerificationError, "ATTRIBUTION_SCHEMA"):
                        verify_receipt.verify_url(changed, value, "source_url", observed)
                    self.assertEqual(observed, [])


class HistoricalReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This immutable metadata-only artifact is fetched before the test job.
        # A missing receipt is an error, never a skipped historical-identity gate.
        cls.path = Path(os.environ["CWC_Q2C_ZIP"])
        cls.report, cls.identity = collision_delta.load_historical_zip(cls.path)
        cls.root = Path(__file__).resolve().parents[1]

    def test_exact_historical_archive_and_changed_bytes_rejected(self):
        self.assertEqual(self.report["snapshot"], collision.SNAPSHOT)
        self.assertEqual(self.report["tree"], collision.TREE)
        self.assertEqual(self.report["repository_exact_collision_count"], 0)
        self.assertEqual(str(self.identity["run_id"]), "45621004026")
        self.assertEqual(str(self.identity["run_attempt"]), "1")
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "tampered.zip"
            raw = bytearray(self.path.read_bytes())
            raw[len(raw) // 2] ^= 1
            tampered.write_bytes(raw)
            with self.assertRaises(collision_delta.DeltaError):
                collision_delta.load_historical_zip(tampered)
            with zipfile.ZipFile(self.path) as archive:
                for omitted in ("identity.json", "SHA256SUMS"):
                    with self.subTest(omitted=omitted):
                        with zipfile.ZipFile(tampered, "w") as replacement:
                            for name in archive.namelist():
                                if name != omitted:
                                    replacement.writestr(name, archive.read(name))
                        with self.assertRaises(collision_delta.DeltaError):
                            collision_delta.load_historical_zip(tampered)

    def test_historical_inventory_binds_complete_snapshot_roster(self):
        entries = collision_delta.tree_entries(self.root, collision.SNAPSHOT)
        verified = collision_delta.validate_historical_inventory(self.report, entries)
        self.assertEqual(set(verified), set(entries))
        self.assertEqual(len(verified), self.report["tracked_blob_count"])
        first = next(iter(entries))
        missing = deepcopy(entries)
        missing.pop(first)
        extra = deepcopy(entries)
        extra["fabricated-path.txt"] = deepcopy(entries[first])
        replacement = deepcopy(entries)
        replacement[first]["git_blob"] = "0" * 40
        for name, changed in (("missing", missing), ("extra", extra), ("blob", replacement)):
            with self.subTest(mutation=name):
                with self.assertRaises(collision_delta.DeltaError):
                    collision_delta.validate_historical_inventory(self.report, changed)
        corrupt = deepcopy(self.report)
        corrupt["inventory"][0]["bytes"] += 1
        with self.assertRaises(collision_delta.DeltaError):
            collision_delta.validate_historical_inventory(corrupt, entries)


class DeltaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Custody Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.needles = {
            ("AVeriTeC", "PRIMARY", "a" * 64): "synthetic exact phrase",
            ("HybridQA", "REPLICATION", "b" * 64): 'caf\u00e9 "quote"',
        }

    def git(self, *args):
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
        )
        return result.stdout.decode().strip()

    def commit(self, files, message):
        for name, raw in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.git("add", "--all")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def test_delta_partitions_add_modify_remove_and_keeps_nonzero_counts(self):
        baseline = self.commit(
            {"same.txt": b"unchanged", "changed.txt": b"original", "removed.txt": b"removed"},
            "baseline",
        )
        before = collision_delta.tree_entries(self.root, baseline)
        (self.root / "removed.txt").unlink()
        target = self.commit(
            {"changed.txt": b"synthetic exact phrase", "added.txt": b"synthetic exact phrase"},
            "target",
        )
        after = collision_delta.tree_entries(self.root, target)
        result = collision_delta.scan_delta(self.root, before, after, self.needles)
        self.assertEqual(result["reused_paths"], ["same.txt"])
        self.assertEqual(result["removed_paths"], ["removed.txt"])
        self.assertEqual([row["path"] for row in result["delta_inventory"]],
                         ["added.txt", "changed.txt"])
        self.assertEqual(result["repository_exact_collision_count"], 1)
        self.assertEqual(result["collision_counts_by_cohort"]["AVeriTeC"]["PRIMARY"], 1)
        self.assertEqual(result["matched_record_ids"], [["AVeriTeC", "PRIMARY", "a" * 64]])
        self.assertTrue(all(row["matched_record_count"] == 1 for row in result["delta_inventory"]))
        self.assertEqual(result["delta_payload_count"], 2)

    def test_nested_and_escaped_payloads_cannot_hide_literal_collisions(self):
        baseline = self.commit({"same.txt": b"unchanged"}, "baseline")
        before = collision_delta.tree_entries(self.root, baseline)
        text = self.needles[("HybridQA", "REPLICATION", "b" * 64)]
        inner = json.dumps({"synthetic": text}, ensure_ascii=True).encode()
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nested.json.gz", gzip.compress(inner))
        target = self.commit({"nested.zip": packed.getvalue()}, "target")
        after = collision_delta.tree_entries(self.root, target)
        result = collision_delta.scan_delta(self.root, before, after, self.needles)
        self.assertEqual(result["repository_exact_collision_count"], 1)
        self.assertEqual(result["collision_counts_by_cohort"]["HybridQA"]["REPLICATION"], 1)
        self.assertEqual(result["delta_payload_count"], 3)
        self.assertEqual(len(result["delta_inventory"][0]["payloads"]), 3)

    def test_matcher_disagreement_and_forged_blob_metadata_rejected(self):
        baseline = self.commit({"same.txt": b"unchanged"}, "baseline")
        before = collision_delta.tree_entries(self.root, baseline)
        target = self.commit({"added.txt": b"synthetic exact phrase"}, "target")
        after = collision_delta.tree_entries(self.root, target)
        original_init = collision.ExactMatcher.__init__

        def disagree(matcher, needles):
            original_init(matcher, needles)
            matcher.reference.clear()

        with patch.object(collision.ExactMatcher, "__init__", disagree):
            with self.assertRaisesRegex(ValueError, "INDEPENDENT_MATCHER_DISAGREEMENT"):
                collision_delta.scan_delta(self.root, before, after, self.needles)
        for field, value in (("bytes", True), ("bytes", 9999), ("git_blob", "0" * 40)):
            with self.subTest(field=field, value=value):
                forged = deepcopy(after)
                forged["added.txt"][field] = value
                with self.assertRaises(ValueError):
                    collision_delta.scan_delta(self.root, before, forged, self.needles)

    def test_dirty_target_wrong_revision_and_unsupported_tree_rejected(self):
        baseline = self.commit({"same.txt": b"unchanged"}, "baseline")
        sha, tree = collision_delta.assert_clean_target(self.root, "HEAD")
        self.assertEqual(sha, baseline)
        self.assertEqual(tree, self.git("rev-parse", "HEAD^{tree}"))
        (self.root / "same.txt").write_bytes(b"dirty")
        with self.assertRaises(collision_delta.DeltaError):
            collision_delta.assert_clean_target(self.root, "HEAD")
        self.commit({}, "modified")
        with self.assertRaises(collision_delta.DeltaError):
            collision_delta.assert_clean_target(self.root, baseline)
        (self.root / "unsupported-link").symlink_to("same.txt")
        target = self.commit({}, "unsupported tree type")
        with self.assertRaises(collision_delta.DeltaError):
            collision_delta.tree_entries(self.root, target)


if __name__ == "__main__":
    unittest.main()
