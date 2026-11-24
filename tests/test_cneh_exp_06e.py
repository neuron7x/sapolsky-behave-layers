"""Independent regression assertions for the frozen observation quotient."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.cneh_exp_06e import assurance, quotient as q, run


class QuotientTests(unittest.TestCase):
    def test_full_continuous_families(self):
        for anchor in q.ANCHORS:
            for lo, hi in q.family_certificate(anchor):
                self.assertLessEqual(F(0), lo)
                self.assertLessEqual(lo, hi)
                self.assertLessEqual(hi, F(1))

    def test_active_gain_alias_exact(self):
        left = q.decimal_lift(q.ANCHORS[0], F(1), F(0), F(100))
        right = q.decimal_lift(q.ANCHORS[0], F(2), F(0), F(100))
        self.assertEqual(left, (F(1, 2), F(1, 4), F(1, 4), F(1, 4)))
        self.assertEqual(right, (F(1, 2), F(1, 4), F(1, 8), F(1, 4)))
        self.assertEqual(left[2], 2*right[2])

    def test_silent_rate_and_active_rate(self):
        for anchor, same in zip(q.ANCHORS, (False, True), strict=True):
            self.assertEqual(q.quotient_key(q.VOLTAGE, anchor, F(100)) ==
                             q.quotient_key(q.VOLTAGE, anchor, F(120)), same)

    def test_domain_and_key_controls(self):
        controls = q.negative_controls()
        self.assertEqual(len(controls), 14)
        self.assertEqual(sum(v == "REJECTED" for v in controls.values()), 7)
        self.assertEqual(controls["SILENT_TAU_CHANGED"], "EQUIVALENT")

    def test_graph_future_unobservability(self):
        report = q.graph_support()
        self.assertEqual(len(report["pairs"]), 16)
        self.assertEqual(set((r["past_mode"], r["future_mode"]) for r in report["pairs"]),
                         {(i, j) for i in range(4) for j in range(4)})
        self.assertEqual(report["future_support_by_past_mode"],
                         {str(i): [0, 1, 2, 3] for i in range(4)})

    def test_complete_panel_and_scope(self):
        report = q.report()
        self.assertEqual(len(report["cases"]), 54)
        self.assertEqual(sum(c["decimal_samples_checked"] for c in report["cases"]), 270)
        self.assertEqual(sorted(x["cases"] for x in report["fibers"]), [9, 9, 9, 27])
        self.assertEqual(len(report["negative_controls"]), 14)
        for flag in ("scientific_promotion_authorized", "source_action_authorized",
                     "closed_loop_authorized"):
            self.assertIs(report[flag], False)
        for name in ("historical_count_observability", "historical_nominal_ood",
                     "historical_noise_width", "historical_2ms_reachability"):
            self.assertEqual(report[name], "FAIL_PRESERVED")
        self.assertEqual(report["closed_loop_efficacy"], "BLOCKED")
        self.assertEqual(report["calibration"], "NOT_TESTED")



class AutonomousQuotientTests(unittest.TestCase):
    """Supplemental engineering properties, not part of the frozen cohort."""

    def test_key_contract(self):
        active, silent = q.ANCHORS
        v, t = q.VOLTAGE, F(100)
        key = q.quotient_key(v, active, t)
        self.assertNotEqual(key, q.quotient_key(v + 1, active, t))
        for i in range(4):
            changed = tuple(x + (F(1, 32) if i == j else 0)
                            for j, x in enumerate(active))
            self.assertNotEqual(key, q.quotient_key(v, changed, t))
        self.assertNotEqual(key, q.quotient_key(v, active, F(120)))
        self.assertEqual(q.quotient_key(v, silent, t),
                         q.quotient_key(v, silent, F(120)))

    def test_generated_interior_and_metamorphic_properties(self):
        # Stable hash-derived rational panel, no host RNG or tuning.
        for index in range(32):
            raw = hashlib.sha256(f"CNEH-06E-ASSURANCE-V1:{index}".encode()).digest()
            z = (F(-1, 3) + F(raw[0] % 17 - 8, 128),
                 F(1 + raw[1] % 32, 128),
                 F(0) if index % 4 == 0 else F(1 + raw[2] % 32, 128),
                 F(1 + raw[3] % 32, 128))
            gain = 1 + F(1 + raw[4] % 63, 64)
            delay = F(1 + raw[5] % 63, 64)
            tau = 100 + F(20 * (1 + raw[6] % 63), 64)
            state = q.decimal_lift(z, gain, delay, tau)
            outer = q.family_certificate(z)
            inner = q.lift_box(z, (gain, gain), (delay, delay), (tau, tau))
            # A point enclosure must be inside the full nuisance enclosure,
            # and both must contain the high-precision lifted state.
            for x, (lo, hi), (a, b) in zip(state, outer, inner, strict=True):
                self.assertLessEqual(lo, a)
                self.assertLessEqual(b, hi)
                self.assertLessEqual(a - q.TOLERANCE, x)
                self.assertLessEqual(x, b + q.TOLERANCE)
                self.assertTrue(0 <= x <= 1)
            # Gain and delay reparametrize a fiber without changing its trace.
            other_gain, other_delay = F(2), F(0)
            other = q.decimal_lift(z, other_gain, other_delay, tau)
            for t in (0, 3, 18, 60, 120):
                left = q.fixtures.current(F(t) + delay, state, tau_n=tau,
                                          nmda_gain=gain)
                right = q.fixtures.current(F(t), other, tau_n=tau,
                                           nmda_gain=other_gain)
                expected = q.quotient_current(t, z, tau)
                self.assertLessEqual(abs(left - right), q.TOLERANCE)
                self.assertLessEqual(abs(left - expected), q.TOLERANCE)
            rate_a = q.quotient_current(120, z, F(100))
            rate_b = q.quotient_current(120, z, F(120))
            if z[2] == 0:
                self.assertEqual(rate_a, rate_b)
            else:
                self.assertGreater(abs(rate_a - rate_b), q.TOLERANCE)

    def test_reversed_boxes_and_exact_types(self):
        z = q.ANCHORS[0]
        good = ((F(1), F(2)), (F(0), F(1)), (F(100), F(120)))
        for index in range(3):
            box = list(good)
            box[index] = tuple(reversed(box[index]))
            with self.assertRaisesRegex(ValueError, "reversed box"):
                q.lift_box(z, *box)
        for bad in (True, 1, 1.0, "1"):
            with self.assertRaises(ValueError):
                q.decimal_lift(z, bad, F(0), F(100))

    def test_targeted_mutants_are_killed(self):
        # The same independent assertions must reject intentional defects.
        # Unexpected exceptions are harness failures, not successful kills.
        key = q.quotient_key
        lift = q.decimal_lift
        current = q.quotient_current

        def drop_active_rate(v, z, t):
            return (*key(v, z, t)[:-1], None)

        def retain_silent_rate(v, z, t):
            return (*key(v, z, t)[:-1], t)

        def drop_amplitude(v, z, t):
            k = key(v, z, t)
            return (k[0], k[1], k[3], k[4], k[5])

        def drop_voltage(v, z, t):
            return key(v, z, t)[1:]

        def wrong_gain(z, gain, delay, tau):
            w, a, n, g = lift(z, gain, delay, tau)
            return w, a, n * gain, g

        def ignore_delay(z, gain, delay, tau):
            return lift(z, gain, F(0), tau)

        def biased_trace(t, z, tau):
            return current(t, z, tau) + F(1, 10**10)

        mutants = (
            ("quotient_key", drop_active_rate, self.test_key_contract),
            ("quotient_key", retain_silent_rate, self.test_key_contract),
            ("quotient_key", drop_amplitude, self.test_key_contract),
            ("quotient_key", drop_voltage, self.test_key_contract),
            ("decimal_lift", wrong_gain, self.test_generated_interior_and_metamorphic_properties),
            ("decimal_lift", ignore_delay, self.test_generated_interior_and_metamorphic_properties),
            ("quotient_current", biased_trace, self.test_generated_interior_and_metamorphic_properties),
        )
        for target, mutant, check in mutants:
            with self.subTest(mutant=mutant.__name__):
                with patch.object(q, target, mutant):
                    with self.assertRaises(AssertionError):
                        check()


class AutonomousEvidenceTests(unittest.TestCase):
    """Fail-closed aggregate admission, with explicitly synthetic unit receipts."""

    def test_aggregate_rejects_tampering(self):
        report = q.report()
        head = "a" * 40
        run_id = "17"
        raw = run.canonical(report)
        cases = {
            "valid": None,
            "missing_arch": "native profile roster",
            "extra_arch": "native profile roster",
            "missing_file": "native evidence file roster",
            "extra_file": "native evidence file roster",
            "truncated_payload": "native raw payload differs",
            "forged_authority": "native raw payload differs",
            "erased_failure": "native raw payload differs",
            "forged_calibration": "native raw payload differs",
            "wrong_head": "native receipt mismatch",
            "wrong_run": "native receipt mismatch",
            "wrong_arch": "native receipt mismatch",
            "wrong_parent": "native receipt mismatch",
            "noncanonical_receipt": "native receipt mismatch",
            "corrupt_parent": "parent archive digest mismatch",
        }
        for case, error in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                parent = root / "synthetic-parent.zip"
                parent.write_bytes(b"unit-test-only parent bytes")
                # Unit-test digest and interpreter only. The native workflow
                # independently authenticates the actual sealed D artifact.
                with patch.object(run, "PARENT_SHA256", run.sha(parent.read_bytes())), \
                     patch.object(run, "PYTHON", platform.python_version()), \
                     redirect_stdout(io.StringIO()):
                    profiles = root / "profiles"
                    for arch in run.ARCHES:
                        folder = profiles / ("cneh06e-" + arch)
                        folder.mkdir(parents=True)
                        (folder / "payload.json").write_bytes(raw)
                        (folder / "receipt.json").write_bytes(
                            run.canonical(run.metadata(head, run_id, arch, raw)))
                    target = profiles / "cneh06e-x86_64"
                    receipt_path = target / "receipt.json"
                    payload_path = target / "payload.json"
                    if case == "missing_arch":
                        shutil.rmtree(target)
                    elif case == "extra_arch":
                        (profiles / "unexpected").mkdir()
                    elif case == "missing_file":
                        receipt_path.unlink()
                    elif case == "extra_file":
                        (target / "extra").write_text("extra", encoding="ascii")
                    elif case == "truncated_payload":
                        payload_path.write_bytes(raw[:-1])
                    elif case in ("forged_authority", "erased_failure", "forged_calibration"):
                        altered = dict(report)
                        if case == "forged_authority":
                            altered["scientific_promotion_authorized"] = True
                        elif case == "erased_failure":
                            altered["historical_noise_width"] = "PASS"
                        else:
                            altered["calibration"] = "PASS"
                        forged = run.canonical(altered)
                        payload_path.write_bytes(forged)
                        # Recompute the digest so mere receipt consistency
                        # cannot pass a fraudulent report.
                        receipt_path.write_bytes(run.canonical(
                            run.metadata(head, run_id, "x86_64", forged)))
                    elif case in ("wrong_head", "wrong_run", "wrong_arch", "wrong_parent"):
                        receipt = json.loads(receipt_path.read_bytes())
                        field, value = {
                            "wrong_head": ("head_sha", "b" * 40),
                            "wrong_run": ("run_id", "18"),
                            "wrong_arch": ("arch", "aarch64"),
                            "wrong_parent": ("parent_sha256", "0" * 64),
                        }[case]
                        receipt[field] = value
                        receipt_path.write_bytes(run.canonical(receipt))
                    elif case == "noncanonical_receipt":
                        receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
                    elif case == "corrupt_parent":
                        parent.write_bytes(b"changed parent")
                    out = root / "aggregate"
                    args = SimpleNamespace(parent=parent, profiles=profiles,
                                           head=head, run_id=run_id, out=out)
                    if error is not None:
                        with self.assertRaisesRegex(ValueError, error):
                            run.aggregate(args)
                        self.assertFalse(out.exists())
                    else:
                        run.aggregate(args)
                        self.assertEqual((out / "payload.json").read_bytes(), raw)
                        summary = json.loads((out / "report.json").read_bytes())
                        self.assertEqual(summary["qualification"],
                                         "PASS_EXACT_SYNTHETIC_QUOTIENT_ONLY")
                        self.assertIs(summary["scientific_promotion_authorized"], False)
                        self.assertEqual(summary["historical_noise_width"], "FAIL_PRESERVED")
                        self.assertEqual(summary["closed_loop_efficacy"], "BLOCKED")
                        self.assertEqual(
                            (out / "SHA256SUMS").read_text(encoding="ascii"),
                            "".join(run.sha((out / name).read_bytes()) + "  " + name + "\n"
                                    for name in ("payload.json", "report.json")))

    def test_metadata_rejects_invalid_identity(self):
        for head, run_id, arch in (("a" * 39, "17", "x86_64"),
                                   ("A" * 40, "17", "x86_64"),
                                   ("a" * 40, "0", "x86_64"),
                                   ("a" * 40, "017", "x86_64"),
                                   ("a" * 40, "17", "arm64")):
            with self.assertRaises(ValueError):
                run.metadata(head, run_id, arch, b"payload")



class MetaAssuranceTests(unittest.TestCase):
    """Attack the autonomous verifier itself; no empirical claims."""

    @classmethod
    def setUpClass(cls):
        cls.baseline = assurance.report()
        assurance.check_governance(cls.baseline)

    def test_governance_rejects_self_issued_authority_and_budget_drift(self):
        cases = [
            ("scientific_promotion_authorized", True, "negative gate changed"),
            ("source_action_authorized", 0, "negative gate changed"),
            ("historical_noise_width", "PASS", "negative gate changed"),
            ("calibration", "PASS", "negative gate changed"),
            ("round_budget", 7, "budget or tolerance"),
            ("tolerance", "1/10", "budget or tolerance"),
            ("unique_cases", 95, "campaign roster"),
            ("status", "FAIL", "nonpassing assurance"),
            ("mutants_killed", 14, "mutation ratchet roster"),
        ]
        for field, value, error in cases:
            with self.subTest(field=field):
                report = deepcopy(self.baseline)
                report[field] = value
                with self.assertRaisesRegex(ValueError, error):
                    assurance.check_governance(report)

    def test_governance_rejects_forged_search_and_mutation_transcripts(self):
        cases = (
            ("duplicate", "duplicate or forged candidate"),
            ("parent", "feedback parent selection"),
            ("false_parent", "unknown feedback parent"),
            ("metric", "baseline oracle invariant"),
            ("survivor", "mutant admission"),
            ("witness_id", "mutation witness provenance"),
            ("witness_budget", "witness reduction budget"),
            ("witness_complexity", "reduced witness identity"),
            ("witness_fault", "unreproducible mutation witness"),
        )
        for case, error in cases:
            with self.subTest(case=case):
                report = deepcopy(self.baseline)
                rows = report["rounds"][0]["evaluations"]
                witness = report["mutation_ratchet"][0]["witness"]
                if case == "duplicate":
                    rows[1] = deepcopy(rows[0])
                elif case == "parent":
                    report["rounds"][1]["parents"] = ["0" * 64]
                elif case == "false_parent":
                    rows[0]["parent_id"] = "0" * 64
                elif case == "metric":
                    rows[0]["trace_error_pA"] = "1"
                elif case == "survivor":
                    report["mutation_ratchet"][0]["status"] = "SURVIVED"
                elif case == "witness_id":
                    witness["original_id"] = "0" * 64
                elif case == "witness_budget":
                    witness["attempts"] = 57
                elif case == "witness_complexity":
                    witness["reduced_complexity"] += 1
                elif case == "witness_fault":
                    witness["reduced"]["faults"] = []
                with self.assertRaisesRegex(ValueError, error):
                    assurance.check_governance(report)

    def test_attempt_bound_profiles_fail_closed_even_with_recomputed_hashes(self):
        head, checkout, run_id, attempt = "a" * 40, "b" * 40, "17", "2"
        original = dict(self.baseline, head_sha=head, checkout_sha=checkout,
                        run_id=run_id, run_attempt=attempt)
        cases = (
            ("valid", None),
            ("mixed_attempt", "raw reconstruction mismatch"),
            ("all_rehashed_forgery", "raw reconstruction mismatch"),
            ("missing_replay", "assurance process roster"),
            ("extra_file", "assurance file roster"),
            ("bad_manifest", "assurance manifest mismatch"),
            ("oversize", "receipt size budget"),
            ("symlink", "nonregular receipt file"),
        )
        for case, error in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                profiles = Path(directory)/"profiles"

                def write(folder, report):
                    folder.mkdir(parents=True, exist_ok=True)
                    raw = assurance.canonical(report)
                    (folder/"report.json").write_bytes(raw)
                    (folder/"SHA256SUMS").write_text(
                        assurance.digest(raw)+"  report.json\n", encoding="ascii")

                for arch in ("x86_64", "aarch64"):
                    for process in ("primary", "replay"):
                        write(profiles/("assurance-cneh06e-"+arch)/process, original)
                target = profiles/"assurance-cneh06e-x86_64"/"primary"
                if case == "mixed_attempt":
                    write(target, dict(original, run_attempt="1"))
                elif case == "all_rehashed_forgery":
                    for folder in profiles.glob("*/*"):
                        write(folder, dict(original, calibration="PASS"))
                elif case == "missing_replay":
                    shutil.rmtree(target.parent/"replay")
                elif case == "extra_file":
                    (target/"unexpected").touch()
                elif case == "bad_manifest":
                    (target/"SHA256SUMS").write_text("invalid", encoding="ascii")
                elif case == "oversize":
                    with (target/"report.json").open("wb") as handle:
                        handle.truncate(assurance.RECEIPT_LIMIT+1)
                elif case == "symlink":
                    outside = Path(directory)/"outside.json"
                    (target/"report.json").rename(outside)
                    (target/"report.json").symlink_to(outside)
                with patch.object(assurance, "report", return_value=self.baseline), \
                     redirect_stdout(io.StringIO()):
                    if error:
                        with self.assertRaisesRegex(ValueError, error):
                            assurance.verify_profiles(profiles, head, checkout, run_id, attempt)
                    else:
                        assurance.verify_profiles(profiles, head, checkout, run_id, attempt)

    def test_regression_does_not_admit_mutually_identical_forged_payloads(self):
        checkout = "b" * 40
        valid = q.report()
        for case, error in (("valid", None), ("forged", "raw reconstruction mismatch"),
                            ("wrong_checkout", "checkout mismatch"),
                            ("wrong_scope", "regression scope"),
                            ("extra_file", "regression file roster")):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report = dict(valid, calibration="PASS") if case == "forged" else valid
                raw = run.canonical(report)
                for arch in ("aarch64", "x86_64"):
                    folder = root/("cneh06e-weekly-"+arch)
                    folder.mkdir()
                    (folder/"payload.json").write_bytes(raw)
                    (folder/"SHA256SUMS").write_text(
                        assurance.digest(raw)+"  payload.json\n", encoding="ascii")
                    (folder/"HEAD").write_text(
                        ("a"*40 if case == "wrong_checkout" else checkout)+"\n",
                        encoding="ascii")
                    (folder/"SCOPE").write_text(
                        ("SCIENTIFIC_ADMISSION" if case == "wrong_scope" else
                         "REGRESSION_ONLY_NOT_SCIENTIFIC_ADMISSION")+"\n", encoding="ascii")
                    if case == "extra_file":
                        (folder/"extra").touch()
                with redirect_stdout(io.StringIO()):
                    if error:
                        with self.assertRaisesRegex(ValueError, error):
                            assurance.verify_regression_profiles(root, checkout)
                    else:
                        assurance.verify_regression_profiles(root, checkout)

if __name__ == "__main__":
    unittest.main()
