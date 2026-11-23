"""Qualification bridge to pinned PR44 and CWC; no replacement control model.

Optional NumPy/SciPy environment is required. The numerical contract freezes
analytic fixtures, not an empirical or neural causal hypothesis. Known invalid
input behavior in the original reference is retained as negative evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any

import numpy as np
import scipy
from scipy import linalg

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_contract() -> dict[str, Any]:
    from experiments.cneh_exp_01.run import strict_json
    return strict_json((HERE / "math_qualification_contract.json").read_bytes())


def _number(value: Any) -> float:
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))
            or not math.isfinite(float(value))):
        raise ValueError("finite real number required; bool is not a measurement")
    return float(value)


def _matrix(value: Any, shape: tuple[int, int] | None = None) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=object)
    except (TypeError, ValueError) as error:
        raise ValueError("rectangular numerical matrix required") from error
    if array.ndim != 2 or 0 in array.shape or (shape is not None and array.shape != shape):
        raise ValueError("invalid matrix dimensions")
    return np.asarray([_number(x) for x in array.flat], dtype=np.float64).reshape(array.shape)


def _vector(value: Any) -> tuple[float, float]:
    row = _matrix([value], (1, 2))[0]
    return float(row[0]), float(row[1])


def _tuples(array: np.ndarray) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(x) for x in row) for row in array)


class QualificationBridge:
    """Validate inputs, then call the existing pinned implementations unchanged."""

    def __init__(self, reference: Path):
        self.contract = load_contract()
        self.numerics = self.contract["numerics"]
        lock = (HERE / "bnsyn-requirements.lock").read_bytes()
        self.dependency_lock_sha256 = digest(lock)
        for name, version in (("numpy", np.__version__), ("scipy", scipy.__version__)):
            matches = re.findall(r"^" + name + r"==([^\s]+)", lock.decode(), re.MULTILINE)
            if matches != [version]:
                raise ValueError(f"{name} runtime does not match the existing dependency lock")
        if reference.is_symlink() or not reference.is_file():
            raise ValueError("PR44 reference must be an explicit regular non-symlink file")
        source = reference.read_bytes()
        if digest(source) != self.contract["pr44"]["sha256"]:
            raise ValueError("PR44 source hash mismatch; no fallback implementation")
        self.reference = ModuleType("cneh_pinned_pr44_linear_reference")
        self.reference.__file__ = str(reference.resolve())
        # Execute the exact verified bytes, avoiding a second source read at import.
        exec(compile(source, str(reference.resolve()), "exec"), self.reference.__dict__)
        for relative, expected in self.contract["cwc"].items():
            path = REPO / relative
            if path.is_symlink() or digest(path.read_bytes()) != expected:
                raise ValueError(f"CWC source hash mismatch: {relative}")
        from cwc.causal import cate, observability, potential_outcomes
        for module in (cate, observability, potential_outcomes):
            relative = Path(module.__file__).resolve().relative_to(REPO).as_posix()
            if relative not in self.contract["cwc"]:
                raise ValueError("CWC module loaded from an unpinned source")
        self.cate = cate
        self.observability = observability
        self.TrialObservation = potential_outcomes.TrialObservation

    def _gramian(self, value: Any) -> np.ndarray:
        array = _matrix(value, (2, 2))
        tolerance = self.numerics["psd_absolute_tolerance"]
        if not np.allclose(array, array.T, atol=tolerance, rtol=0):
            raise ValueError("Gramian must be symmetric")
        if float(linalg.eigvalsh(array)[0]) < -tolerance:
            raise ValueError("Gramian must be positive semidefinite")
        return array

    def finite_gramians(self, a: Any, b: Any, c_a: Any, c_b: Any, *,
                        horizon: int, observation_variance: float) -> dict[str, np.ndarray]:
        matrices = [_matrix(value, (2, 2)) for value in (a, b, c_a, c_b)]
        if type(horizon) is not int or not 1 <= horizon <= self.numerics["maximum_horizon"]:
            raise ValueError("horizon outside qualified finite integer domain")
        variance = _number(observation_variance)
        if variance <= 0:
            raise ValueError("observation variance must be positive")
        result = self.reference.finite_gramians(*map(_tuples, matrices), horizon=horizon,
                                                observation_variance=variance)
        if set(result) != {"Wc", "Wo_A", "Wo_B", "Wo_joint"}:
            raise ValueError("unexpected PR44 Gramian schema")
        return {name: self._gramian(value) for name, value in result.items()}

    def hankel_singular_values(self, wc: Any, wo: Any) -> np.ndarray:
        matrices = [self._gramian(value) for value in (wc, wo)]
        result = self.reference.hankel_singular_values(*map(_tuples, matrices))
        values = np.asarray(_vector(result))
        if np.any(values < 0) or values[0] > values[1]:
            raise ValueError("invalid PR44 Hankel spectrum")
        # The reference's trace-minus-discriminant formula can lose the small
        # singular value through cancellation even for finite positive Gramians.
        # A stable factor/SVD oracle qualifies the delegated answer; it never
        # silently substitutes a different answer for the pinned implementation.
        roots = []
        for matrix in matrices:
            eigenvalues, vectors = linalg.eigh(matrix)
            roots.append(vectors @ np.diag(np.sqrt(np.maximum(eigenvalues, 0.0))))
        expected = np.sort(linalg.svdvals(roots[1].T @ roots[0]))
        if not np.allclose(values, expected, atol=self.numerics["absolute_tolerance"],
                           rtol=self.numerics["relative_tolerance"]):
            raise ValueError("PR44 Hankel spectrum disagrees with stable SVD oracle")
        return values

    def parameter_information(self, *, theta: float, a0: float, a1: float,
                              actuator_gain: float, initial: Any, fixed_actions: Any,
                              observation_variance: float) -> float:
        parameters = dict(theta=_number(theta), a0=_number(a0), a1=_number(a1),
                          actuator_gain=_number(actuator_gain), initial=_vector(initial),
                          observation_variance=_number(observation_variance))
        if parameters["observation_variance"] <= 0:
            raise ValueError("observation variance must be positive")
        if not isinstance(fixed_actions, (list, tuple)) or not 1 <= len(fixed_actions) <= self.numerics["maximum_horizon"]:
            raise ValueError("fixed open-loop action sequence required")
        parameters["fixed_actions"] = [_vector(action) for action in fixed_actions]
        result = _number(self.reference.theta_regression_information_open_loop(**parameters))
        if result < 0:
            raise ValueError("negative parameter Fisher information")
        return result

    def local_identifiability(self, jacobian: Any, covariance: Any):
        j = _matrix(jacobian)
        sigma = _matrix(covariance, (len(j), len(j)))
        if not np.allclose(sigma, sigma.T, atol=self.numerics["absolute_tolerance"], rtol=0):
            raise ValueError("covariance must be symmetric")
        if float(linalg.eigvalsh(sigma)[0]) <= 0:
            raise ValueError("covariance must be positive definite")
        certificate = self.observability.local_first_order_identifiability(
            j, covariance=sigma, rank_tolerance=self.numerics["rank_tolerance"])
        if (not all(math.isfinite(x) for x in certificate.singular_values)
                or certificate.information_min_eigenvalue is None
                or not math.isfinite(certificate.information_min_eigenvalue)):
            raise ValueError("nonfinite CWC identifiability certificate")
        if certificate.numerical_rank == certificate.parameter_count:
            # Full column rank of J does not certify numerical accuracy after
            # forming J.T Sigma^-1 J. Squaring its condition number can erase
            # the smallest eigenvalue. Preserve CWC's result only if it agrees
            # relatively with a stable whitened-SVD oracle on this full-rank domain.
            whitened = linalg.solve_triangular(linalg.cholesky(sigma, lower=True), j, lower=True)
            singular = linalg.svdvals(whitened)
            minimum = float(singular[-1] ** 2)
            condition = float((singular[0] / singular[-1]) ** 2)
            measured_condition = certificate.information_condition_number
            if (minimum <= 0 or not math.isfinite(minimum) or not math.isfinite(condition)
                    or certificate.information_min_eigenvalue <= 0
                    or measured_condition is None or not math.isfinite(measured_condition)
                    or not math.isclose(certificate.information_min_eigenvalue, minimum,
                                        abs_tol=0, rel_tol=self.numerics["relative_tolerance"])
                    or not math.isclose(measured_condition, condition, abs_tol=0,
                                        rel_tol=self.numerics["relative_tolerance"])):
                raise ValueError("full Jacobian rank does not qualify numerically unstable Fisher spectrum")
        return certificate

    def trial_values(self, observations: list[Any], assignments: dict[str, tuple[int, str]], *,
                     training_unit_ids: tuple[str, ...] = (),
                     context_features: tuple[str, ...] = ("predecision_stratum",)) -> dict[str, float]:
        """Validate the exact four-cell fixture, not real-world trial provenance."""
        if context_features != ("predecision_stratum",):
            raise ValueError("post-outcome or undeclared context feature")
        if any(type(unit) is not str or not unit or type(cell) is not tuple or len(cell) != 2
               or type(cell[0]) is not int or cell[0] not in (0, 1)
               or type(cell[1]) is not str or cell[1] not in ("0", "1")
               for unit, cell in assignments.items()):
            raise ValueError("invalid randomized fixture assignment")
        units = [row.unit_id for row in observations]
        if (len(units) != 4 or len(set(units)) != 4 or set(units) != set(assignments)
                or set(assignments.values()) != {(u, str(a)) for u in (0, 1) for a in (0, 1)}):
            raise ValueError("incomplete randomized four-cell fixture; confounding not excluded")
        if set(units).intersection(training_unit_ids):
            raise ValueError("outcome-model training/evaluation unit leakage")
        predictions = observations[0].outcome_model
        if predictions not in ({"0": 0.0, "1": 1.0}, {"0": 0.5, "1": 0.5}):
            raise ValueError("outcome predictions must use a frozen analytic fixture")
        for row in observations:
            _number(row.utility)
            if (row.context != "predecision" or row.action != assignments[row.unit_id][1]
                    or _number(row.propensity) != 0.5
                    or set(row.outcome_model) != {"0", "1"}):
                raise ValueError("fixture assignment, positivity or context mismatch")
            if row.outcome_model != predictions:
                raise ValueError("unit-dependent outcome model violates frozen prediction boundary")
            for value in row.outcome_model.values():
                _number(value)
        values = {}
        for action in ("0", "1"):
            policy = {"predecision": {"0": float(action == "0"), "1": float(action == "1")}}
            values[f"ips_do_{action}"] = _number(self.cate.ips_policy_value(observations, policy))
            values[f"dr_do_{action}"] = _number(self.cate.doubly_robust_policy_value(observations, policy))
        return values


def _certificate_payload(certificate: Any) -> dict[str, Any]:
    payload = asdict(certificate)
    for key in ("condition_number", "information_condition_number"):
        value = payload[key]
        if value is not None and not math.isfinite(value):
            if math.isnan(value) or value < 0:
                raise ValueError("invalid certificate condition number")
            payload[key] = None
            payload[key + "_status"] = "SINGULAR"
    return payload


def intervention_fixture(bridge: QualificationBridge, model: str):
    """Exact enumeration of the two preregistered structural equations."""
    if model not in ("causal", "confounded"):
        raise ValueError("unknown frozen countermodel")
    laws = {"observe": {}, "do_0": {}, "do_1": {}}
    records, assignments = [], {}
    for u in (0, 1):
        x = u
        y = x if model == "causal" else u
        laws["observe"][x, y] = laws["observe"].get((x, y), 0.0) + 0.5
        for action in (0, 1):
            x = action  # Intervention replaces X=U; Y equation remains unchanged.
            y = x if model == "causal" else u
            law = laws[f"do_{action}"]
            law[x, y] = law.get((x, y), 0.0) + 0.5
            unit = f"{model}:u{u}:a{action}"
            prediction = {"0": 0.0, "1": 1.0} if model == "causal" else {"0": 0.5, "1": 0.5}
            records.append(bridge.TrialObservation(unit, "predecision", str(action), float(y), 0.5, prediction))
            assignments[unit] = (u, str(action))
    return laws, records, assignments


def _open_loop_response(parameters: dict[str, Any], theta: float) -> np.ndarray:
    """Independent matrix-power response oracle; never a research runner."""
    a = np.asarray([[parameters["a0"], theta], [-theta, parameters["a1"]]])
    initial = np.asarray(parameters["initial"])
    actions = np.asarray(parameters["fixed_actions"])
    return np.concatenate([
        np.linalg.matrix_power(a, t + 1) @ initial
        + parameters["actuator_gain"] * sum(
            (np.linalg.matrix_power(a, t - k) @ actions[k] for k in range(t + 1)),
            start=np.zeros(2))
        for t in range(len(actions))])


def qualify(reference: Path) -> dict[str, Any]:
    bridge = QualificationBridge(reference)
    contract, tolerance = bridge.contract, bridge.numerics
    checks: dict[str, Any] = {}

    def close(name: str, actual: Any, expected: Any, *, finite_difference: bool = False):
        prefix = "finite_difference_" if finite_difference else ""
        checks[name] = {
            "pass": bool(np.allclose(actual, expected, atol=tolerance[prefix + "absolute_tolerance"],
                                     rtol=tolerance[prefix + "relative_tolerance"])),
            "actual": np.asarray(actual).tolist(), "expected": np.asarray(expected).tolist(),
        }

    def rejects(name: str, function):
        rejected = False
        try:
            function()
        except ValueError:
            rejected = True
        close(name, rejected, True)

    fixture = contract["lti_fixture"]
    a, b, ca, cb = (np.asarray(fixture[key]) for key in ("A", "B", "C_A", "C_B"))
    horizon, variance = fixture["horizon"], fixture["observation_variance"]
    grams = bridge.finite_gramians(a, b, ca, cb, horizon=horizon, observation_variance=variance)
    reach = np.concatenate([np.linalg.matrix_power(a, t) @ b for t in range(horizon)], axis=1)
    oa = np.concatenate([ca @ np.linalg.matrix_power(a, t) for t in range(horizon)]) / math.sqrt(variance)
    ob = np.concatenate([cb @ np.linalg.matrix_power(a, t) for t in range(horizon)]) / math.sqrt(variance)
    observation = np.concatenate([oa, ob])
    close("Wc_block_factor", grams["Wc"], reach @ reach.T)
    close("Wo_A_block_factor", grams["Wo_A"], oa.T @ oa)
    close("Wo_B_block_factor", grams["Wo_B"], ob.T @ ob)
    close("Wo_joint_block_factor", grams["Wo_joint"], observation.T @ observation)
    hsv = bridge.hankel_singular_values(grams["Wc"], grams["Wo_joint"])
    close("Hankel_independent_block_SVD", hsv, np.sort(linalg.svdvals(observation @ reach))[-2:])
    for index, transform in enumerate(fixture["similarity_transforms"]):
        s = np.asarray(transform)
        inverse = linalg.inv(s)
        transformed = bridge.finite_gramians(s @ a @ inverse, s @ b, ca @ inverse, cb @ inverse,
                                             horizon=horizon, observation_variance=variance)
        close(f"similarity_{index}_Wc", transformed["Wc"], s @ grams["Wc"] @ s.T)
        close(f"similarity_{index}_Wo", transformed["Wo_joint"], inverse.T @ grams["Wo_joint"] @ inverse)
        close(f"similarity_{index}_Hankel", bridge.hankel_singular_values(transformed["Wc"], transformed["Wo_joint"]), hsv)
    zero = np.zeros((2, 2))
    close("zero_actuation_Wc", bridge.finite_gramians(a, zero, ca, cb, horizon=horizon,
                                                    observation_variance=variance)["Wc"], zero)
    close("zero_observation_Wo", bridge.finite_gramians(a, b, zero, zero, horizon=horizon,
                                                       observation_variance=variance)["Wo_joint"], zero)
    isolated = bridge.finite_gramians(np.diag([0.7, 0.8]), b, ca, zero, horizon=horizon,
                                      observation_variance=variance)
    close("unobserved_isolated_coordinate", isolated["Wo_joint"][1, 1], 0.0)

    fisher = contract["fisher_fixture"]
    j, covariance = np.asarray(fisher["jacobian"]), np.asarray(fisher["covariance"])
    certificate = bridge.local_identifiability(j, covariance)
    information = j.T @ linalg.solve(covariance, j, assume_a="pos")
    eigenvalues = linalg.eigvalsh(information)
    close("Fisher_full_rank", certificate.numerical_rank, 2)
    close("Fisher_covariance_min_eigenvalue", certificate.information_min_eigenvalue, eigenvalues[0])
    close("Fisher_covariance_condition", certificate.information_condition_number, eigenvalues[-1] / eigenvalues[0])
    scaled = bridge.local_identifiability(j, fisher["covariance_rescaling"] * covariance)
    close("Fisher_covariance_rescaling", scaled.information_min_eigenvalue,
          eigenvalues[0] / fisher["covariance_rescaling"])
    deficient = bridge.local_identifiability(fisher["rank_deficient_jacobian"], covariance)
    close("Fisher_rank_deficiency", deficient.numerical_rank, 1)
    close("CWC_local_certificate_has_no_causal_authority", certificate.causal_authority_granted, False)
    rejects("singular_covariance_rejected", lambda: bridge.local_identifiability(j, np.zeros((3, 3))))
    rejects("indefinite_covariance_rejected", lambda: bridge.local_identifiability(j, np.diag([1, 1, -1])))

    parameters = {key: contract["open_loop_parameter_fixture"][key] for key in
                  ("theta", "a0", "a1", "actuator_gain", "initial", "fixed_actions", "observation_variance")}
    step, theta = tolerance["finite_difference_step"], parameters["theta"]
    derivative = (_open_loop_response(parameters, theta + step) - _open_loop_response(parameters, theta - step)) / (2 * step)
    parameter_certificate = bridge.local_identifiability(derivative[:, None], np.eye(len(derivative)) * parameters["observation_variance"])
    close("parameter_Fisher_open_loop_oracle", bridge.parameter_information(**parameters),
          parameter_certificate.information_min_eigenvalue, finite_difference=True)
    zero_parameters = {**parameters, "initial": [0.0, 0.0],
                       "fixed_actions": [[0.0, 0.0] for _ in parameters["fixed_actions"]]}
    close("parameter_Fisher_zero_excitation", bridge.parameter_information(**zero_parameters), 0.0)
    close("state_observable_despite_zero_parameter_information", linalg.eigvalsh(grams["Wo_joint"])[0] > 0, True)

    family, effects = {}, {}
    for model in ("causal", "confounded"):
        family[model], rows, assignments = intervention_fixture(bridge, model)
        values = bridge.trial_values(rows, assignments)
        effects[model] = values
        for estimator in ("ips", "dr"):
            close(f"{model}_{estimator}_intervention_effect", values[f"{estimator}_do_1"] - values[f"{estimator}_do_0"],
                  contract["countermodel_fixture"]["expected_effects"][model])
    observational = bridge.observability.finite_identifiability_certificate(
        family, selected_actions=["observe"], tolerance=tolerance["finite_law_total_variation_tolerance"])
    interventional = bridge.observability.finite_identifiability_certificate(
        family, selected_actions=["do_0", "do_1"], tolerance=tolerance["finite_law_total_variation_tolerance"])
    close("countermodels_observational_equivalence", observational.minimum_pair_separation, 0.0)
    close("countermodels_actual_intervention_separation", interventional.minimum_pair_separation, 0.5)
    close("observational_countermodels_unresolved", len(observational.unresolved_pairs), 1)
    close("interventional_countermodels_resolved", len(interventional.unresolved_pairs), 0)
    close("CWC_finite_certificate_has_no_causal_authority", interventional.causal_authority_granted, False)
    _, confounded_rows, assignments = intervention_fixture(bridge, "confounded")
    observational_rows = [row for row in confounded_rows if assignments[row.unit_id][0] == int(row.action)]
    observational_assignments = {row.unit_id: assignments[row.unit_id] for row in observational_rows}
    false_randomization_value = bridge.cate.ips_policy_value(
        observational_rows, {"predecision": {"0": 0.0, "1": 1.0}})
    close("false_randomization_negative_is_biased", false_randomization_value, 1.0)
    rejects("confounded_observations_rejected_as_trial", lambda: bridge.trial_values(observational_rows, observational_assignments))
    rejects("same_unit_training_leakage_rejected", lambda: bridge.trial_values(
        confounded_rows, assignments, training_unit_ids=(confounded_rows[0].unit_id,)))
    rejects("post_outcome_context_leakage_rejected", lambda: bridge.trial_values(
        confounded_rows, assignments, context_features=("observed_outcome",)))

    shifted = contract["misspecification_fixture"]
    nominal = bridge.reference.mv(_tuples(_matrix(shifted["nominal_A"], (2, 2))), _vector(shifted["state"]))
    actual = bridge.reference.mv(_tuples(_matrix(shifted["shifted_A"], (2, 2))), _vector(shifted["state"]))
    residual = float(linalg.norm(np.asarray(actual) - nominal))
    close("OOD_nominal_model_rejected", residual > tolerance["absolute_tolerance"], True)

    raw_nan = bridge.reference.hankel_singular_values(((math.nan, 0.0), (0.0, 1.0)), bridge.reference.EYE)
    raw_inf = bridge.reference.finite_gramians(_tuples(a), _tuples(b), _tuples(ca), _tuples(cb),
                                               horizon=1, observation_variance=math.inf)
    known_failures = {
        "NaN_Hankel": {"input": "NaN in Wc[0,0]", "raw_return": list(raw_nan), "raw_input_rejected": False},
        "infinite_variance": {"input": "+Infinity observation variance", "raw_Wo_joint": raw_inf["Wo_joint"], "raw_input_rejected": False},
    }
    ill_conditioned = ((1e20, 0.0), (0.0, 1.0))
    known_failures["postregistration_finite_Hankel_cancellation"] = {
        "input": "Wc=diag(1e20,1), Wo=I", "raw_return": list(bridge.reference.hankel_singular_values(ill_conditioned, bridge.reference.EYE)),
        "independent_diagonal_answer": [1.0, 1e10], "raw_input_rejected": False,
        "origin": "independent adversarial review after fixture registration; retained counterexample, no threshold change",
    }
    ill_jacobian = [[1.0, 1.0], [1.0, 1.0 + 1e-8]]
    raw_information = bridge.observability.local_first_order_identifiability(
        ill_jacobian, covariance=np.eye(2), rank_tolerance=tolerance["rank_tolerance"])
    known_failures["postregistration_CWC_Fisher_cancellation"] = {
        "input": "J=[[1,1],[1,1+1e-8]], covariance=I", "raw_certificate": _certificate_payload(raw_information),
        "stable_SVD_minimum_information": float(linalg.svdvals(np.asarray(ill_jacobian))[-1] ** 2),
        "information_status": "NUMERICALLY_UNQUALIFIED_DESPITE_FULL_JACOBIAN_RANK",
        "origin": "independent adversarial review after fixture registration; no threshold change",
    }
    rejected = 0
    for call in (
        lambda: bridge.hankel_singular_values(((math.nan, 0.0), (0.0, 1.0)), np.eye(2)),
        lambda: bridge.finite_gramians(a, b, ca, cb, horizon=1, observation_variance=math.inf),
    ):
        try:
            call()
        except ValueError:
            rejected += 1
    close("wrapper_rejects_known_raw_invalid_inputs", rejected, 2)
    rejects("finite_Hankel_cancellation_rejected", lambda: bridge.hankel_singular_values(ill_conditioned, np.eye(2)))
    rejects("full_rank_Fisher_cancellation_rejected", lambda: bridge.local_identifiability(ill_jacobian, np.eye(2)))
    return {
        "schema": "cneh-reused-math-qualification-v1",
        "status": "PASS" if all(check["pass"] for check in checks.values()) else "FAIL",
        "authority": "ANALYTIC_FIXTURES_ONLY", "scientific_promotion_authorized": False,
        "causal_attribution_qualified": False, "neural_estimators_qualified": False,
        "reference_direct_use_qualified": False,
        "known_raw_reference_failures": known_failures,
        "checks": checks, "fisher_certificate": _certificate_payload(certificate),
        "rank_deficient_certificate": _certificate_payload(deficient),
        "countermodel_certificates": {"observational": asdict(observational), "interventional": asdict(interventional)},
        "intervention_values": effects, "OOD_residual": residual,
        "confounding_negative": {"false_randomization_IPS_do_1": false_randomization_value,
                                  "actual_enumerated_do_1": effects["confounded"]["ips_do_1"],
                                  "authority": "INVALID_RANDOMIZATION_ASSUMPTION"},
        "source_sha256": {"pr44_reference": contract["pr44"]["sha256"],
                          "bridge": digest(Path(__file__).read_bytes()),
                          "contract": digest((HERE / "math_qualification_contract.json").read_bytes()),
                          "bnsyn-requirements.lock": bridge.dependency_lock_sha256,
                          **contract["cwc"]},
        "runtime": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__},
    }


def verify_report(out: Path, reference: Path) -> dict[str, Any]:
    """Exact deterministic replay of this qualification; not independent replication."""
    from experiments.cneh_exp_01.run import canonical, strict_json
    if out.is_symlink() or not out.is_file():
        raise ValueError("qualification report must be a regular non-symlink file")
    observed = strict_json(out.read_bytes())
    expected = qualify(reference)
    if canonical(observed) != canonical(expected):
        raise ValueError("qualification report/source/runtime mismatch")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        report = verify_report(args.out, args.reference)
    else:
        report = qualify(args.reference)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    print(report["status"] + ": reused analytic fixtures; scientific promotion blocked")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
