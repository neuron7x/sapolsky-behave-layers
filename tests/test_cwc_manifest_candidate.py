"""Synthetic engineering controls; no source admission or model evidence.

Round-trip controls stub only the already-qualified acquisition/custody/source
reconstruction boundary and Git target, using real temporary files. They execute
both new implementations, the unchanged declaration/byte binder, and the final
rereads. Hosted qualification separately runs the genuine pinned-source path.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from experiments.cwc_manifest_candidate import candidate as builder
from experiments.cwc_manifest_candidate import verify_candidate as verifier
from experiments.cwc_closure import preflight as binding
from experiments.cwc_source_admission import acquisition, verify_receipt
from experiments.real_transfer_01 import contract, preflight, readiness, source_intake

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CandidateControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Required actual immutable archive; absence is a failure, never a skip.
        cls.history = Path(os.environ["CWC_Q2C_ZIP"])
        raw = cls.history.read_bytes()
        if len(raw) != 579686 or sha(raw) != verify_receipt.ZIP_SHA:
            raise RuntimeError("Historical fixture identity mismatch")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cwc-candidate-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repository"
        self.root.mkdir()
        self.cache = self.root / "source-cache-candidate"
        self.cache.mkdir()
        sources, traces = [], []
        for family, name, ref, url, _, _ in source_intake.SOURCES:
            raw = ("SYNTHETIC_CONTROL_ONLY:"+name).encode()
            (self.cache/name).write_bytes(raw)
            row = {"family": family, "name": name, "ref": ref, "canonical_url": url,
                   "byte_length": len(raw), "sha256": sha(raw)}
            if name != "wikitable_links.zip":
                row["git_blob"] = source_intake.git_blob(raw)
            sources.append(row)
            traces.append({"name": name, "completed_at": "2026-01-01T00:00:00.000000Z"})
        cohorts = {}
        for family, groups in binding.COHORT_COUNTS.items():
            cohorts[family] = {}
            for name, count in groups.items():
                hashes = sorted(sha(f"SYNTHETIC:{family}:{name}:{index}".encode()) for index in range(count))
                cohorts[family][name] = {"count": count, "record_hashes": hashes,
                                         "cohort_sha256": sha("\n".join(hashes).encode())}
        self.projection = {"sources": sorted(sources, key=lambda row: row["name"]), "cohorts": cohorts}
        self.trace = {"sources": traces}
        self.target = {"target_commit": "a"*40, "target_tree": "b"*40}
        self.custody = {"source_projection": self.projection, "hybridqa_inventory": {"tables": []},
                        "averitec_inventory": {"records": []},
                        "repository_collision_binding": {**self.target, "target_roster_sha256": "c"*64,
                                                         "repository_exact_collision_count": 7}}
        self.acquisition_path = self.base / "acquisition.json"
        self.custody_path = self.base / "custody.json"
        self.verification_path = self.base / "verification.json"
        self.candidate_path = self.base / "candidate.json"
        self.write(self.acquisition_path, self.trace)
        self.write(self.custody_path, self.custody)
        self.fresh = {"status": "SYNTHETIC_FRESH_RECONSTRUCTION", **self.target,
                      "receipt_sha256": sha(self.custody_path.read_bytes()),
                      "target_roster_sha256": "c"*64, "repository_exact_collision_count": 7}
        self.write(self.verification_path, self.fresh)
        with self.dependencies():
            self.envelope = builder.build(self.root, self.cache, self.acquisition_path, self.custody_path,
                                          self.verification_path, self.history)
        builder.write_exclusive(self.root, self.candidate_path, self.envelope)

    @staticmethod
    def write(path, value):
        path.write_bytes(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()+b"\n")

    @contextmanager
    def dependencies(self):
        with ExitStack() as stack:
            patched = {}
            for name, module, attribute, result in (
                ("builder_target", builder, "assert_target", self.target),
                ("target", verifier, "target_identity", tuple(self.target.values())),
                ("projection", binding, "reconstruct", self.projection),
                ("fresh", verify_receipt, "verify", self.fresh),
                ("acquisition", acquisition, "validate_receipt", self.trace),
            ):
                patched[name] = stack.enter_context(mock.patch.object(module, attribute, return_value=result))
            yield patched

    def verify(self):
        return verifier.verify(self.root, self.cache, self.candidate_path, self.acquisition_path,
                               self.custody_path, self.verification_path, self.history)

    def reject_payload(self, payload):
        self.write(self.candidate_path, payload)
        with self.dependencies(), self.assertRaisesRegex(verifier.CandidateVerificationError,
                                                        "CANDIDATE_RECONSTRUCTION_MISMATCH"):
            self.verify()

    def test_blocked_flags_do_not_make_legacy_manifest_inert(self):
        manifest = deepcopy(self.envelope["candidate_fields"])
        for source in manifest["sources"]:
            source["license"] = "SYNTHETIC_SCHEMA_CONTROL_NO_ADMISSION"
        manifest.update({"status": "BLOCKED", "source_manifest_admitted": False,
                         "model_execution_authorized": False})
        # This accepted control demonstrates the actual permissive legacy hazard.
        self.assertIsNone(preflight.validate_source_manifest(manifest))

    def test_envelope_and_extracted_draft_rejected_by_original_readiness(self):
        for payload in (self.envelope, self.envelope["candidate_fields"]):
            with self.subTest(envelope="schema" in payload):
                with self.assertRaises(contract.ContractError):
                    preflight.validate_source_manifest(payload)
                self.write(self.candidate_path, payload)
                result = readiness.analyze(root=ROOT, source_manifest_path=self.candidate_path)
                self.assertEqual(result["execution_status"], "NOT_TESTED")
                self.assertTrue(any(code.startswith("SOURCE_MANIFEST_INVALID:") for code in result["blockers"]))

    def test_complete_synthetic_round_trip_reaches_final_rereads(self):
        with self.dependencies() as checks:
            result = self.verify()
        self.assertEqual(checks["target"].call_count, 2)
        self.assertEqual(checks["acquisition"].call_count, 2)
        self.assertEqual(checks["fresh"].call_count, 1)
        self.assertEqual(result["cohort_records"], 1076)
        self.assertEqual(result["repository_exact_collision_count"], 7)
        self.assertEqual(result["candidate_sha256"], sha(self.candidate_path.read_bytes()))
        self.assertEqual({key: result[key] for key in verifier.AUTHORITY}, verifier.AUTHORITY)
        fields = self.envelope["candidate_fields"]
        self.assertTrue(all(row["license"] is None for row in fields["sources"]))
        self.assertEqual(fields["collision_audit"], {"repository_exact_collision_count": 7,
                         "training_exact_collision_count": None, "training_collision_audit_complete": False})
        self.assertEqual(self.envelope["scope"]["training_corpus_provenance"], "UNKNOWN")
        self.assertEqual(sha(verifier.canonical(verifier.PUBLISHER_DECLARATIONS)),
                         "da9e3c06f15c76e5094cb54e1e85db6c1624e1512a20e7976dd3778a42bd0650")

    def test_extra_free_text_rejected_at_every_public_layer(self):
        for path in ((), ("candidate_fields",), ("candidate_fields", "collision_audit"),
                     ("publisher_declarations", 0), ("evidence_bindings",), ("scope",), ("admission",)):
            with self.subTest(path=path):
                changed = deepcopy(self.envelope)
                target = changed
                for key in path:
                    target = target[key]
                target["unbound_raw_text"] = "SYNTHETIC_PRIVATE_SENTINEL"
                self.reject_payload(changed)

    def test_authority_type_and_admission_escalation_rejected(self):
        for path, value in (
            (("authority", "model_execution_authorized"), True),
            (("authority", "scientific_verdict"), "PASS"),
            (("authority", "source_manifest_admitted"), 0),
            (("admission", "use_context"), "NONCOMMERCIAL"),
            (("admission", "missing_oldid_is_rejection_threshold"), True),
            (("candidate_fields", "sources", 0, "license"), "CC-BY-NC-4.0"),
            (("candidate_fields", "collision_audit", "repository_exact_collision_count"), 7.0),
            (("scope", "training_corpus_provenance"), "AUDITED"),
        ):
            with self.subTest(path=path):
                changed = deepcopy(self.envelope)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.reject_payload(changed)

    def test_source_declaration_identity_and_observed_time_substitution_rejected(self):
        for field, value in (("path", "other-cache/averitec_dev.json"), ("ref", "d"*40),
                             ("sha256", "d"*64), ("byte_length", 1),
                             ("acquired_at", "2026-01-02T00:00:00.000000Z")):
            with self.subTest(field=field):
                changed = deepcopy(self.envelope)
                changed["candidate_fields"]["sources"][0][field] = value
                self.reject_payload(changed)

    def test_coherent_membership_and_order_substitutions_rejected(self):
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                changed = deepcopy(self.envelope)
                group = changed["candidate_fields"]["cohorts"]["AVeriTeC"]["CALIBRATION"]
                if replacement:
                    group["record_hashes"][0] = "f"*64
                    group["record_hashes"].sort()
                else:
                    group["record_hashes"].reverse()
                group["cohort_sha256"] = sha("\n".join(group["record_hashes"]).encode())
                self.reject_payload(changed)

    def test_receipt_inventory_and_current_tree_bindings_reject_substitution(self):
        for path, value in ((("acquisition_receipt", "sha256"), "0"*64),
                            (("custody_receipt", "byte_length"), 1),
                            (("source_projection_sha256",), "1"*64),
                            (("attribution_inventory_sha256",), "2"*64),
                            (("historical_zip_sha256",), "3"*64),
                            (("current_tree", "target_commit"), "4"*40),
                            (("current_tree", "target_roster_sha256"), "5"*64)):
            with self.subTest(path=path):
                changed = deepcopy(self.envelope)
                target = changed["evidence_bindings"]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.reject_payload(changed)

    def test_claimed_pass_never_replaces_fresh_custody_reconstruction(self):
        supplied = {**self.fresh, "status": "PASS", "source_manifest_admitted": True}
        self.write(self.verification_path, supplied)
        changed = deepcopy(self.envelope)
        raw = self.verification_path.read_bytes()
        changed["evidence_bindings"]["verification_receipt"] = {"byte_length": len(raw), "sha256": sha(raw)}
        self.write(self.candidate_path, changed)
        with self.dependencies() as calls:
            with self.assertRaisesRegex(verifier.CandidateVerificationError, "UNVERIFIED_OR_SUBSTITUTED"):
                self.verify()
            self.assertEqual(calls["fresh"].call_count, 1)
        with self.dependencies() as calls:
            calls["fresh"].side_effect = verify_receipt.VerificationError("SYNTHETIC_FRESH_REJECTION")
            with self.assertRaisesRegex(verify_receipt.VerificationError, "SYNTHETIC_FRESH_REJECTION"):
                self.verify()

    def test_actual_source_byte_change_rejected_by_unchanged_binder(self):
        path = self.cache / "averitec_dev.json"
        original = path.read_bytes()
        path.write_bytes(b"X"+original[1:])
        with self.dependencies(), self.assertRaisesRegex(binding.BindingError, "SOURCE_BYTES_CHANGED"):
            self.verify()

    def test_evidence_change_during_verification_rejected_at_tail(self):
        original = verifier.compare_candidate

        def change_after_comparison(actual, expected):
            original(actual, expected)
            self.acquisition_path.write_bytes(self.acquisition_path.read_bytes()+b" ")

        with self.dependencies(), mock.patch.object(verifier, "compare_candidate", side_effect=change_after_comparison):
            with self.assertRaisesRegex(verifier.CandidateVerificationError, "RECEIPT_CHANGED"):
                self.verify()

    def test_target_change_during_verification_rejected_at_tail(self):
        with self.dependencies() as calls:
            calls["target"].side_effect = [tuple(self.target.values()), ("d"*40, self.target["target_tree"])]
            with self.assertRaisesRegex(verifier.CandidateVerificationError, "TARGET_CHANGED"):
                self.verify()

    def test_regular_input_controls_reject_links_fifo_and_byte_budget(self):
        path = self.base / "input.json"
        path.write_bytes(b"{}\n")
        alias = self.base / "alias.json"
        for module in (builder, verifier):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.read_regular(path, 3), b"{}\n")
                with self.assertRaises(ValueError):
                    module.read_regular(path, 2)
                alias.symlink_to(path)
                with self.assertRaises(ValueError):
                    module.read_regular(alias, 3)
                alias.unlink()
                os.link(path, alias)
                with self.assertRaises(ValueError):
                    module.read_regular(path, 3)
                alias.unlink()
                os.mkfifo(alias)
                with self.assertRaises(ValueError):
                    module.read_regular(alias, 3)
                alias.unlink()

    def test_cache_roster_containment_and_lexical_aliases_rejected(self):
        for module in (builder, verifier):
            for alias in (str(self.cache)+"/.", str(self.root)+"//source-cache-candidate",
                          str(self.root)+"/../repository/source-cache-candidate"):
                with self.subTest(module=module.__name__, alias=alias), self.assertRaises(ValueError):
                    module.validate_cache(str(self.root), alias)
            with self.assertRaises(ValueError):
                module.validate_cache(self.base, self.cache)
        extra = self.cache/"extra.json"
        extra.write_bytes(b"{}")
        for module in (builder, verifier):
            with self.assertRaises(ValueError):
                module.validate_cache(self.root, self.cache)
        extra.unlink()
        real = self.cache/"averitec_dev.json"
        moved = self.base/"averitec_dev.json"
        real.rename(moved)
        real.symlink_to(moved)
        for module in (builder, verifier):
            with self.assertRaises(ValueError):
                module.validate_cache(self.root, self.cache)

    def test_exclusive_output_and_reserved_repository_paths_rejected(self):
        for index, module in enumerate((builder, verifier)):
            out = self.base/f"new-{index}.json"
            module.write_exclusive(self.root, out, {"synthetic": True})
            before = out.read_bytes()
            for invalid in (out, self.root/"candidate.json", self.root/"SOURCE_MANIFEST.json",
                            self.base/"SOURCE_MANIFEST.json"):
                with self.subTest(module=module.__name__, path=invalid), self.assertRaises(ValueError):
                    module.write_exclusive(self.root, invalid, {"synthetic": False})
            self.assertEqual(out.read_bytes(), before)

    def test_output_parent_swap_cannot_follow_symlink_after_validation(self):
        for index, (module, attribute) in enumerate(((builder, "open_parent"), (verifier, "parent_descriptor"))):
            parent = self.base/f"safe-{index}"
            parent.mkdir()
            original = getattr(module, attribute)

            def swap(path, *, original=original, parent=parent):
                parent.rename(parent.with_name(parent.name+"-old"))
                parent.symlink_to(self.root, target_is_directory=True)
                return original(path)

            with mock.patch.object(module, attribute, side_effect=swap):
                with self.assertRaises(OSError):
                    module.write_exclusive(self.root, parent/"escaped.json", {"synthetic": True})
            self.assertFalse((self.root/"escaped.json").exists())

    def test_strict_json_rejects_duplicates_and_nonfinite_values(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"value":NaN}', b'{"value":Infinity}'):
            self.candidate_path.write_bytes(raw)
            with self.dependencies(), self.assertRaises(ValueError):
                self.verify()

    def test_executed_module_bytes_must_equal_actual_git_object(self):
        repo = self.base/"git-control"
        repo.mkdir()
        path = repo/"module.py"
        path.write_bytes(b"# synthetic committed module\n")

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

        git("init", "--quiet")
        git("add", "module.py")
        git("-c", "user.name=Synthetic Control", "-c", "user.email=synthetic@example.invalid",
            "commit", "--quiet", "-m", "Synthetic code binding control")
        commit = git("rev-parse", "HEAD").decode().strip()
        verifier.committed_bytes(repo, commit, "module.py")
        path.write_bytes(b"# substituted module\n")
        with self.assertRaisesRegex(verifier.CandidateVerificationError, "EXECUTED_CODE_NOT_COMMITTED"):
            verifier.committed_bytes(repo, commit, "module.py")
        with self.assertRaisesRegex(verifier.CandidateVerificationError, "DIRTY_TARGET"):
            verifier.target_identity(repo)


if __name__ == "__main__":
    unittest.main()
