from __future__ import annotations

from cwc.governance.finite_strata_transport import target_mean_lcb_under_finite_strata_shift


def _cert(source_values, source_strata, target_strata):
    return target_mean_lcb_under_finite_strata_shift(
        source_values,
        source_strata,
        target_strata,
        lower=0.0,
        upper=1.0,
        delta=0.05,
        conditional_mean_invariance_attested=True,
        source_target_independence_attested=True,
        stratum_schema_digest="attack-schema",
        invariance_authority_digest="attack-invariance",
    )


def main() -> int:
    n = 500
    source_values = [0.0] * n + [1.0] * n
    source_strata = ["low"] * n + ["high"] * n
    target_strata = ["low"] * 490 + ["high"] * 10

    cert = _cert(source_values, source_strata, target_strata)
    naive_source_mean = sum(source_values) / len(source_values)
    if not (cert.target_mean_lower < 0.08 and naive_source_mean == 0.5):
        raise SystemExit(
            f"MATH_IGNORE_TARGET_MIX_SURVIVED lcb={cert.target_mean_lower} source={naive_source_mean}"
        )

    try:
        _cert([0.5, 0.6], ["seen", "seen"], ["seen", "unseen"])
    except ValueError as exc:
        if "positivity/support failure" not in str(exc):
            raise
    else:
        raise SystemExit("MATH_SMOOTH_UNSEEN_TARGET_STRATUM_SURVIVED")

    print("DGC-MATH-V2J: PASS — target-mix reuse and unseen-stratum smoothing attacks killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
