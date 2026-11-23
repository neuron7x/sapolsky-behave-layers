"""Explicit locked NumPy/SciPy qualification; missing dependencies fail, never skip."""
from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from experiments.cneh_exp_01 import math_qualification as qualification


class ReusedMathQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference_path = Path(os.environ["CNEH_PR44_REFERENCE"])

    def setUp(self):
        self.bridge = qualification.QualificationBridge(self.reference_path)
        self.fixture = self.bridge.contract["lti_fixture"]

    def grams(self, **overrides):
        kwargs = {"horizon": self.fixture["horizon"],
                  "observation_variance": self.fixture["observation_variance"], **overrides}
        return self.bridge.finite_gramians(*(self.fixture[k] for k in ("A", "B", "C_A", "C_B")), **kwargs)

    def test_frozen_oracles_pass_without_scientific_promotion(self):
        report = qualification.qualify(self.reference_path)
        self.assertEqual(report["status"], "PASS")
        self.assertGreaterEqual(len(report["checks"]), 30)
        self.assertTrue(all(check["pass"] for check in report["checks"].values()))
        for field in ("scientific_promotion_authorized", "causal_attribution_qualified",
                      "neural_estimators_qualified", "reference_direct_use_qualified"):
            self.assertIs(report[field], False)
        self.assertEqual(report["authority"], "ANALYTIC_FIXTURES_ONLY")
        json.dumps(report, allow_nan=False)

    def test_source_tamper_and_symlink_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            altered = root / "reference.py"
            altered.write_bytes(self.reference_path.read_bytes() + b"\nraise AssertionError('executed unpinned source')\n")
            with self.assertRaisesRegex(ValueError, "source hash"):
                qualification.QualificationBridge(altered)
            linked = root / "linked.py"
            linked.symlink_to(self.reference_path.resolve())
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                qualification.QualificationBridge(linked)

    def test_dependency_version_drift_rejected(self):
        with patch.object(qualification.np, "__version__", "0.0.0"):
            with self.assertRaisesRegex(ValueError, "dependency lock"):
                qualification.QualificationBridge(self.reference_path)

    def test_existing_reference_is_actually_delegated_to(self):
        reference = self.bridge.reference
        with patch.object(reference, "finite_gramians", wraps=reference.finite_gramians) as delegated:
            grams = self.grams()
            self.assertEqual(delegated.call_count, 1)
        with patch.object(reference, "hankel_singular_values", wraps=reference.hankel_singular_values) as delegated:
            self.bridge.hankel_singular_values(grams["Wc"], grams["Wo_joint"])
            self.assertEqual(delegated.call_count, 1)

    def test_known_raw_failures_remain_visible_and_wrapper_rejects_first(self):
        raw = self.bridge.reference
        nan_gramian = ((math.nan, 0.0), (0.0, 1.0))
        self.assertEqual(raw.hankel_singular_values(nan_gramian, raw.EYE), (0.0, 0.0))
        infinite = raw.finite_gramians(raw.EYE, raw.EYE, raw.EYE, raw.EYE,
                                      horizon=1, observation_variance=math.inf)
        self.assertEqual(infinite["Wo_joint"], raw.ZERO)
        with patch.object(raw, "hankel_singular_values", side_effect=AssertionError("delegated invalid input")):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.bridge.hankel_singular_values(nan_gramian, np.eye(2))
        with patch.object(raw, "finite_gramians", side_effect=AssertionError("delegated invalid input")):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.grams(observation_variance=math.inf)

    def test_gramian_domain_checks_reject_nonfinite_bool_shape_and_invalid_horizon(self):
        for value in (math.nan, math.inf, -math.inf, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.grams(observation_variance=value)
                with self.assertRaises(ValueError):
                    self.bridge.hankel_singular_values([[value, 0], [0, 1]], np.eye(2))
        for horizon in (0, -1, True, 1.5, 65):
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                self.grams(horizon=horizon)
        for matrix in ([], [[1]], [[1, 0], [0]], [[1, 1], [0, 1]], [[-1, 0], [0, 1]]):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                self.bridge.hankel_singular_values(matrix, np.eye(2))

    def test_finite_hankel_cancellation_cannot_destroy_small_singular_value(self):
        wc = ((1e20, 0.0), (0.0, 1.0))
        raw = self.bridge.reference.hankel_singular_values(wc, self.bridge.reference.EYE)
        self.assertEqual(raw, (0.0, 1e10))
        with self.assertRaisesRegex(ValueError, "stable SVD oracle"):
            self.bridge.hankel_singular_values(wc, np.eye(2))
        # Singular PSD is admissible: an exact zero must not be confused with
        # losing a positive singular value through catastrophic cancellation.
        actual = self.bridge.hankel_singular_values(np.diag([4.0, 0.0]), np.eye(2))
        np.testing.assert_allclose(actual, [0.0, 2.0], atol=0, rtol=0)

    def test_covariance_rank_and_singular_certificate_are_distinct(self):
        fixture = self.bridge.contract["fisher_fixture"]
        full = self.bridge.local_identifiability(fixture["jacobian"], fixture["covariance"])
        deficient = self.bridge.local_identifiability(fixture["rank_deficient_jacobian"], fixture["covariance"])
        self.assertEqual(full.state, "LOCAL_FIRST_ORDER_IDENTIFIABLE")
        self.assertEqual(deficient.state, "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE")
        self.assertFalse(full.causal_authority_granted)
        zero = self.bridge.local_identifiability(np.zeros((3, 2)), fixture["covariance"])
        payload = qualification._certificate_payload(zero)
        self.assertEqual(payload["numerical_rank"], 0)
        self.assertIsNone(payload["condition_number"])
        self.assertEqual(payload["condition_number_status"], "SINGULAR")
        json.dumps(payload, allow_nan=False)
        for covariance in (np.zeros((3, 3)), np.diag([1, 1, -1]),
                           [[1, 1, 0], [0, 1, 0], [0, 0, 1]],
                           [[math.nan, 0, 0], [0, 1, 0], [0, 0, 1]]):
            with self.subTest(covariance=covariance), self.assertRaises(ValueError):
                self.bridge.local_identifiability(fixture["jacobian"], covariance)

    def test_zero_excitation_does_not_inherit_state_observability(self):
        specification = self.bridge.contract["open_loop_parameter_fixture"]
        kwargs = {key: specification[key] for key in
                  ("theta", "a0", "a1", "actuator_gain", "initial", "fixed_actions", "observation_variance")}
        excited = self.bridge.parameter_information(**kwargs)
        zero = self.bridge.parameter_information(**{**kwargs, "initial": [0, 0],
                                                     "fixed_actions": [[0, 0]] * len(kwargs["fixed_actions"])})
        self.assertGreater(excited, 0)
        self.assertEqual(zero, 0)
        self.assertGreater(np.linalg.eigvalsh(self.grams()["Wo_joint"])[0], 0)
        for invalid in (math.nan, math.inf, True, 0, -1):
            with self.subTest(variance=invalid), self.assertRaises(ValueError):
                self.bridge.parameter_information(**{**kwargs, "observation_variance": invalid})

    def test_full_rank_does_not_qualify_numerically_cancelled_fisher(self):
        for perturbation in (1e-8, 1e-7):
            jacobian = [[1.0, 1.0], [1.0, 1.0 + perturbation]]
            raw = self.bridge.observability.local_first_order_identifiability(
                jacobian, covariance=np.eye(2), rank_tolerance=self.bridge.numerics["rank_tolerance"])
            self.assertEqual(raw.numerical_rank, 2)
            with self.subTest(perturbation=perturbation), self.assertRaisesRegex(ValueError, "unstable Fisher"):
                self.bridge.local_identifiability(jacobian, np.eye(2))

    def test_actual_do_replacement_separates_observationally_equivalent_models(self):
        causal, causal_rows, causal_assignments = qualification.intervention_fixture(self.bridge, "causal")
        confounded, confounded_rows, confounded_assignments = qualification.intervention_fixture(self.bridge, "confounded")
        self.assertEqual(causal["observe"], confounded["observe"])
        self.assertNotEqual(causal["do_0"], confounded["do_0"])
        self.assertEqual(causal["do_0"], {(0, 0): 1.0})
        self.assertEqual(confounded["do_0"], {(0, 0): 0.5, (0, 1): 0.5})
        for model, rows, assignments, expected in (
            ("causal", causal_rows, causal_assignments, 1.0),
            ("confounded", confounded_rows, confounded_assignments, 0.0),
        ):
            with self.subTest(model=model):
                values = self.bridge.trial_values(rows, assignments)
                self.assertEqual(values["ips_do_1"] - values["ips_do_0"], expected)
                self.assertEqual(values["dr_do_1"] - values["dr_do_0"], expected)

    def test_observational_confounding_is_not_a_randomized_trial(self):
        _, rows, assignments = qualification.intervention_fixture(self.bridge, "confounded")
        observed = [row for row in rows if assignments[row.unit_id][0] == int(row.action)]
        observed_assignments = {row.unit_id: assignments[row.unit_id] for row in observed}
        # False randomization assumption yields 1 instead of the actual do(1)=0.5.
        misleading = self.bridge.cate.ips_policy_value(observed, {"predecision": {"0": 0, "1": 1}})
        self.assertEqual(misleading, 1.0)
        with self.assertRaisesRegex(ValueError, "confounding"):
            self.bridge.trial_values(observed, observed_assignments)

    def test_leakage_and_nonfinite_trial_utility_are_rejected(self):
        _, rows, assignments = qualification.intervention_fixture(self.bridge, "causal")
        with self.assertRaisesRegex(ValueError, "leakage"):
            self.bridge.trial_values(rows, assignments, training_unit_ids=(rows[0].unit_id,))
        with self.assertRaisesRegex(ValueError, "post-outcome"):
            self.bridge.trial_values(rows, assignments, context_features=("observed_outcome",))
        with self.assertRaisesRegex(ValueError, "unit-dependent"):
            self.bridge.trial_values([*rows[:-1], replace(rows[-1], outcome_model={"0": 0.5, "1": 0.5})], assignments)
        boolean_cell = dict(assignments)
        boolean_cell[rows[0].unit_id] = (False, "0")
        with self.assertRaisesRegex(ValueError, "assignment"):
            self.bridge.trial_values(rows, boolean_cell)
        for utility in (math.nan, math.inf, True):
            corrupted = [replace(rows[0], utility=utility), *rows[1:]]
            with self.subTest(utility=utility), self.assertRaisesRegex(ValueError, "finite"):
                self.bridge.trial_values(corrupted, assignments)

    def test_cli_emits_finite_report_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "qualification.json"
            command = [sys.executable, str(Path(qualification.__file__)),
                       "--reference", str(self.reference_path), "--out", str(out)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = out.read_bytes()
            self.assertEqual(json.loads(original)["status"], "PASS")
            verified = subprocess.run(command + ["--verify"], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(out.read_bytes(), original)
            forged = json.loads(original)
            forged["scientific_promotion_authorized"] = True
            out.write_text(json.dumps(forged))
            denied = subprocess.run(command + ["--verify"], capture_output=True, text=True)
            self.assertNotEqual(denied.returncode, 0)


if __name__ == "__main__":
    unittest.main()
