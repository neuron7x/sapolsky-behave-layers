"""Engineering fixtures for closure admission; no fixture is scientific evidence."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from experiments.cwc_closure import preflight as p
from experiments.real_transfer_01 import source_intake as intake


def fixture_groups():
    groups = {}
    for family, sizes in p.COHORT_COUNTS.items():
        groups[family] = {}
        for name, count in sizes.items():
            hashes = [p.digest(f"fixture-{family}-{name}-{i}".encode()) for i in range(count)]
            groups[family][name] = {
                "count": count, "cohort_sha256": p.digest("\n".join(hashes).encode()),
                "record_hashes": hashes,
            }
    return groups


def source_fixture(root):
    cache = root/"cache"
    cache.mkdir()
    items = []
    for family, name, ref, url, _, _ in intake.SOURCES:
        raw = ("synthetic binding fixture: "+name).encode()
        (cache/name).write_bytes(raw)
        items.append({"family": family, "name": name, "ref": ref, "canonical_url": url,
                      "byte_length": len(raw), "sha256": p.digest(raw)})
    projection = {"sources": items, "cohorts": fixture_groups()}
    declaration = {"sources": [
        {**{key: value for key, value in item.items() if key != "name"},
         "path": "cache/"+item["name"], "upstream_commit_sha": item["ref"]} for item in items],
        "cohorts": deepcopy(projection["cohorts"])}
    return cache, projection, declaration


def model_fixture(root):
    manifest = {"runner_version": "synthetic-fixture-not-a-model", "decoding_parameters": {},
                "decoding_parameters_sha256": p.digest(b"{}"),
                "training_corpus_provenance": "UNKNOWN", "artifact_bindings": {}}
    for key in p.FIELDS:
        name = key+".bin"
        raw = ("not a real model: "+key).encode()
        (root/name).write_bytes(raw)
        manifest[key] = p.digest(raw)
        manifest["artifact_bindings"][key] = {"path": name, "byte_length": len(raw)}
    return manifest


class ClosureTests(unittest.TestCase):
    def test_terminal_plan_dependency_dag_and_weights(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root/"experiments/cwc_closure/PLAN.json").read_text())
        rows = plan["scoring"]["weights"]
        self.assertEqual(sum(row["points"] for row in rows), 100)
        known = set()
        for row in rows:
            self.assertNotIn(row["id"], known)
            self.assertTrue(set(row["requires"]).issubset(known))
            self.assertTrue(row["exit"])
            known.add(row["id"])
        self.assertEqual(plan["scientific_contract"]["cohorts"], p.COHORT_COUNTS)
        self.assertEqual(plan["scientific_contract"]["policies"], list(p.readiness.REQUIRED_POLICIES))
        self.assertEqual(plan["authority"]["merge"], "OWNER_ONLY")
        self.assertIs(plan["authority"]["primary_tuning"], False)

    def test_exact_source_declaration_and_coherent_nonmember(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache, projection, declaration = source_fixture(root)
            self.assertTrue(p.compare_source_declaration(root, cache, declaration, projection))
            forged = deepcopy(declaration)
            cohort = forged["cohorts"]["HybridQA"]["PRIMARY"]
            cohort["record_hashes"][0] = p.digest(b"another internally consistent nonmember")
            cohort["cohort_sha256"] = p.digest("\n".join(cohort["record_hashes"]).encode())
            self.assertEqual(p.cohort_shape(forged["cohorts"]), 1076)
            with self.assertRaisesRegex(p.BindingError, "SOURCE_COHORT_MEMBERSHIP_MISMATCH"):
                p.compare_source_declaration(root, cache, forged, projection)
            changed = deepcopy(declaration)
            group = changed["cohorts"]["AVeriTeC"]["CALIBRATION"]
            group["record_hashes"].reverse()
            group["cohort_sha256"] = p.digest("\n".join(group["record_hashes"]).encode())
            with self.assertRaisesRegex(p.BindingError, "SOURCE_COHORT_MEMBERSHIP_MISMATCH"):
                p.compare_source_declaration(root, cache, changed, projection)

    def test_source_roster_and_identity_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache, projection, declaration = source_fixture(root)
            for mode in ("duplicate", "missing", "wrong_ref", "wrong_sha", "wrong_length",
                         "wrong_commit", "path_alias", "escape", "wrong_url"):
                with self.subTest(mode=mode):
                    bad = deepcopy(declaration)
                    item = bad["sources"][0]
                    if mode == "duplicate":
                        bad["sources"][1] = deepcopy(item)
                    elif mode == "missing":
                        bad["sources"].pop()
                    elif mode == "wrong_ref":
                        item["ref"] = "0"*40
                    elif mode == "wrong_sha":
                        item["sha256"] = "0"*64
                    elif mode == "wrong_length":
                        item["byte_length"] += 1
                    elif mode == "wrong_commit":
                        item["upstream_commit_sha"] = None
                    elif mode == "path_alias":
                        item["path"] = "cache/./"+Path(item["path"]).name
                    elif mode == "escape":
                        item["path"] = "../"+Path(item["path"]).name
                    else:
                        item["canonical_url"] = "https://example.invalid/source"
                    with self.assertRaises((p.BindingError, OSError)):
                        p.compare_source_declaration(root, cache, bad, projection)
            (cache/projection["sources"][0]["name"]).write_bytes(b"changed")
            with self.assertRaises(p.BindingError):
                p.compare_source_declaration(root, cache, declaration, projection)

    def test_invalid_cohort_types_duplicates_and_digest(self):
        groups = fixture_groups()
        self.assertEqual(p.cohort_shape(groups), 1076)
        for mode in ("boolean", "count", "missing", "overlap", "digest"):
            bad = deepcopy(groups)
            primary = bad["AVeriTeC"]["PRIMARY"]
            if mode == "boolean":
                primary["count"] = True
            elif mode == "count":
                primary["count"] -= 1
            elif mode == "missing":
                del bad["HybridQA"]
            elif mode == "overlap":
                primary["record_hashes"][0] = bad["AVeriTeC"]["CALIBRATION"]["record_hashes"][0]
                primary["cohort_sha256"] = p.digest("\n".join(primary["record_hashes"]).encode())
            else:
                primary["cohort_sha256"] = "0"*64
            with self.subTest(mode=mode), self.assertRaises(p.BindingError):
                p.cohort_shape(bad)

    def test_model_byte_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = model_fixture(root)
            self.assertEqual(set(p.bind_model_artifacts(root, manifest)), set(p.FIELDS))
            for mode in ("missing", "digest", "length", "boolean", "alias", "escape", "extra"):
                bad = deepcopy(manifest)
                key = p.FIELDS[0]
                if mode == "missing":
                    bad["artifact_bindings"].pop(key)
                elif mode == "digest":
                    bad[key] = "0"*64
                elif mode == "length":
                    bad["artifact_bindings"][key]["byte_length"] += 1
                elif mode == "boolean":
                    bad["artifact_bindings"][key]["byte_length"] = True
                elif mode == "alias":
                    bad["artifact_bindings"][key] = deepcopy(bad["artifact_bindings"][p.FIELDS[1]])
                    bad[key] = bad[p.FIELDS[1]]
                elif mode == "escape":
                    bad["artifact_bindings"][key]["path"] = "../outside"
                else:
                    bad["artifact_bindings"]["extra"] = {}
                with self.subTest(mode=mode), self.assertRaises((ValueError, OSError)):
                    p.bind_model_artifacts(root, bad)
            path = root/manifest["artifact_bindings"][p.FIELDS[0]]["path"]
            raw = path.read_bytes()
            path.write_bytes(bytes([raw[0]^1])+raw[1:])
            with self.assertRaisesRegex(p.BindingError, "MODEL_ARTIFACT_DIGEST"):
                p.bind_model_artifacts(root, manifest)

    def test_nonregular_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = model_fixture(root)
            path = root/manifest["artifact_bindings"][p.FIELDS[0]]["path"]
            other = root/"target"
            path.rename(other)
            path.symlink_to(other)
            with self.assertRaises(p.BindingError):
                p.bind_model_artifacts(root, manifest)
            path.unlink()
            path.mkdir()
            with self.assertRaises(p.BindingError):
                p.bind_model_artifacts(root, manifest)

    def test_manifest_strict_json_and_missing_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/"manifest.json"
            for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'', b'{'):
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    p.load_manifest(root, "manifest.json")
            outcome = p.audit(root, root/"cache")
            self.assertEqual(outcome["status"], "NOT_TESTED")
            self.assertIs(outcome["scientific_promotion_authorized"], False)
            self.assertIs(outcome["model_execution_authorized"], False)
            self.assertIn("SOURCE_BINDING_MISSING_FILE_OR_MANIFEST", outcome["blockers"])
            self.assertIn("MODEL_BINDING_MISSING_FILE_OR_MANIFEST", outcome["blockers"])

    def test_exact_committed_bytes_not_worktree_assertion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                subprocess.run(["git", "-C", str(root), *args], check=True,
                               capture_output=True, timeout=30)
            git("init")
            git("config", "user.name", "CWC Fixture")
            git("config", "user.email", "fixture@example.invalid")
            path = root/"fixture.json"
            path.write_bytes(b'{"a":1}')
            git("add", "fixture.json")
            git("commit", "-m", "fixture")
            p.committed_bytes(root, "fixture.json", path.read_bytes())
            path.write_bytes(b'{"a":2}')
            with self.assertRaises(p.BindingError):
                p.committed_bytes(root, "fixture.json", path.read_bytes())
            with self.assertRaises(p.BindingError):
                p.committed_bytes(root, "absent", b"fixture")


if __name__ == "__main__":
    unittest.main()
