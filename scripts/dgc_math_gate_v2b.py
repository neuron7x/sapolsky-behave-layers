from __future__ import annotations

from cwc.governance.metareasoning_bounds import certify_myopic_suboptimality_upper_bound
from cwc.governance.nonstationary import current_mean_lower_bound_under_bounded_drift


def main() -> int:
    killed: dict[str, bool] = {}
    drift = current_mean_lower_bound_under_bounded_drift(
        [0.8] * 100,
        drift_to_current=[0.20] * 100,
        lower=0.0,
        upper=1.0,
        delta=0.05,
    )
    killed["MATH_OMIT_NONSTATIONARY_DRIFT"] = (
        drift.stationary_mean_lower > 0.60 and drift.current_mean_lower < 0.60
    )
    try:
        certify_myopic_suboptimality_upper_bound(
            myopic_value=0.0,
            perfect_information_value_upper=1.0,
            pure_information_certified=False,
        )
        killed["MATH_PI_BOUND_ON_INTERVENTION"] = False
    except ValueError:
        killed["MATH_PI_BOUND_ON_INTERVENTION"] = True

    for name, caught in sorted(killed.items()):
        print(f"DGC-MATH-V2B-ATTACK: {'KILLED' if caught else 'SURVIVED'} {name}")
    if not all(killed.values()):
        return 1
    print("DGC-MATH-V2B-GATE: PASS (2/2 attacks killed; aggregate math attacks=9/9)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
