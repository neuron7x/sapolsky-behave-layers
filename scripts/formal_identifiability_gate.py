from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from cwc.causal.observability import (
    finite_identifiability_certificate,
    local_first_order_identifiability,
    minimum_cost_separating_design,
)


def reference_family():
    return {
        "direct": {
            "observe": {"off": 0.5, "on": 0.5},
            "do_x": {"off": 0.9, "on": 0.1},
            "do_z": {"off": 0.5, "on": 0.5},
        },
        "mediated": {
            "observe": {"off": 0.5, "on": 0.5},
            "do_x": {"off": 0.1, "on": 0.9},
            "do_z": {"off": 0.5, "on": 0.5},
        },
        "alternate": {
            "observe": {"off": 0.5, "on": 0.5},
            "do_x": {"off": 0.9, "on": 0.1},
            "do_z": {"off": 0.2, "on": 0.8},
        },
    }


def run_gate() -> dict:
    family = reference_family()
    observational = finite_identifiability_certificate(
        family, selected_actions=["observe"]
    )
    interventional = finite_identifiability_certificate(
        family, selected_actions=["do_x", "do_z"]
    )
    design = minimum_cost_separating_design(
        family, costs={"observe": 0.1, "do_x": 2.0, "do_z": 1.0}
    )
    local_good = local_first_order_identifiability(
        [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    )
    local_bad = local_first_order_identifiability([[1.0, 2.0], [2.0, 4.0]])

    predicates = {
        "observation_only_rejected": observational.state
        == "NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL",
        "interventions_separate_family": interventional.state
        == "FINITE_IDENTIFIABLE_UNDER_DECLARED_CHANNEL",
        "minimum_design_exact": design.actions == ("do_x", "do_z"),
        "full_rank_local_passes": local_good.state == "LOCAL_FIRST_ORDER_IDENTIFIABLE",
        "rank_deficient_local_rejected": local_bad.state
        == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE",
        "no_certificate_promotes_causal_authority": not any(
            x.causal_authority_granted
            for x in (observational, interventional, local_good, local_bad)
        ),
    }
    if not all(predicates.values()):
        raise SystemExit("FORMAL-IDENTIFIABILITY-GATE: FAIL " + json.dumps(predicates, sort_keys=True))
    return {
        "state": "PASS",
        "predicates": predicates,
        "observational": asdict(observational),
        "interventional": asdict(interventional),
        "minimum_design": asdict(design),
        "local_full_rank": asdict(local_good),
        "local_rank_deficient": asdict(local_bad),
    }


def self_test() -> dict:
    family = reference_family()
    killed: dict[str, bool] = {}

    duplicate = {name: {a: dict(law) for a, law in actions.items()} for name, actions in family.items()}
    duplicate["duplicate"] = {a: dict(law) for a, law in family["direct"].items()}
    killed["duplicate_model"] = bool(
        finite_identifiability_certificate(duplicate).unresolved_pairs
    )

    omitted = finite_identifiability_certificate(family, selected_actions=["do_x"])
    killed["omitted_separating_intervention"] = bool(omitted.unresolved_pairs)

    try:
        bad = {name: {a: dict(law) for a, law in actions.items()} for name, actions in family.items()}
        bad["direct"]["do_x"] = {"off": 0.8, "on": 0.8}
        finite_identifiability_certificate(bad)
        killed["malformed_probability_law"] = False
    except ValueError:
        killed["malformed_probability_law"] = True

    try:
        minimum_cost_separating_design(
            family, costs={"observe": 0.1, "do_x": 0.0, "do_z": 1.0}
        )
        killed["zero_cost"] = False
    except ValueError:
        killed["zero_cost"] = True

    killed["rank_deficiency"] = (
        local_first_order_identifiability([[1.0, 2.0], [2.0, 4.0]]).state
        == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
    )

    try:
        local_first_order_identifiability(
            [[1.0, 0.0], [0.0, 1.0]], covariance=[[1.0, 0.0], [0.0, 0.0]]
        )
        killed["non_pd_covariance"] = False
    except ValueError:
        killed["non_pd_covariance"] = True

    if not all(killed.values()):
        raise SystemExit("FORMAL-IDENTIFIABILITY-SELF-TEST: FAIL " + json.dumps(killed, sort_keys=True))
    return {"state": "PASS", "killed": killed, "kill_count": sum(killed.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = self_test() if args.self_test else run_gate()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
