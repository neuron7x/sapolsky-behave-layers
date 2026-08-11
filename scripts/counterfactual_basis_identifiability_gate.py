from __future__ import annotations

import itertools
import json
from dataclasses import asdict

from cwc.counterfactual.identifiability import (
    audit_counterfactual_basis_orthogonality,
    certify_counterfactual_basis,
)
from cwc.counterfactual.model import CANDIDATES


FAMILIES = ("LINEAR", "CONTEXT", "NONLINEAR")


def factorial_rows() -> list[dict[str, float]]:
    names = (*CANDIDATES, "context")
    return [
        dict(zip(names, values, strict=True))
        for values in itertools.product((-1.0, 1.0), repeat=len(names))
    ]


def run_gate() -> dict:
    full = factorial_rows()
    confounded = [row for row in full if row["C"] == row["A"]]

    full_results = {family: certify_counterfactual_basis(family, full) for family in FAMILIES}
    confounded_results = {
        family: certify_counterfactual_basis(family, confounded) for family in FAMILIES
    }
    full_orthogonality = {
        family: audit_counterfactual_basis_orthogonality(family, full) for family in FAMILIES
    }
    confounded_orthogonality = {
        family: audit_counterfactual_basis_orthogonality(family, confounded) for family in FAMILIES
    }

    predicates = {
        "full_factorial_all_identifiable": all(
            result.certificate.state == "LOCAL_FIRST_ORDER_IDENTIFIABLE"
            for result in full_results.values()
        ),
        "confounded_slice_all_rank_deficient": all(
            result.certificate.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
            for result in confounded_results.values()
        ),
        "confounded_slice_returns_nullspace": all(
            len(result.certificate.nullspace_basis) > 0 for result in confounded_results.values()
        ),
        "full_factorial_gram_is_32I": all(
            audit.orthogonal_equal_norm
            and abs(audit.expected_diagonal - 32.0) <= 1e-12
            and abs(audit.gram_condition_number - 1.0) <= 1e-12
            for audit in full_orthogonality.values()
        ),
        "confounding_breaks_orthogonality": all(
            not audit.orthogonal_equal_norm for audit in confounded_orthogonality.values()
        ),
        "no_structural_certificate_grants_causal_authority": all(
            not result.certificate.causal_authority_granted
            for result in (*full_results.values(), *confounded_results.values())
        ),
    }
    if not all(predicates.values()):
        raise SystemExit(
            "COUNTERFACTUAL-BASIS-IDENTIFIABILITY: FAIL "
            + json.dumps(predicates, sort_keys=True)
        )

    return {
        "state": "PASS",
        "predicates": predicates,
        "full_factorial_rows": len(full),
        "confounded_rows": len(confounded),
        "full_factorial": {k: asdict(v) for k, v in full_results.items()},
        "full_factorial_orthogonality": {k: asdict(v) for k, v in full_orthogonality.items()},
        "confounded_slice_C_equals_A": {k: asdict(v) for k, v in confounded_results.items()},
        "confounded_orthogonality": {k: asdict(v) for k, v in confounded_orthogonality.items()},
    }


def main() -> None:
    print(json.dumps(run_gate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
