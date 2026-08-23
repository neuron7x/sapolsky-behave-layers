from cwc.governance.combinatorial_coverage import CoverageCase, Factor, FactorSchema, certify_t_way_coverage, require_coverage


def main():
    schema = FactorSchema((
        Factor("a", ("0", "1")),
        Factor("b", ("0", "1")),
        Factor("c", ("0", "1")),
    ))
    cases = (
        CoverageCase("1", (("a", "0"), ("b", "0"), ("c", "0"))),
        CoverageCase("2", (("a", "0"), ("b", "1"), ("c", "1"))),
        CoverageCase("3", (("a", "1"), ("b", "0"), ("c", "1"))),
        CoverageCase("4", (("a", "1"), ("b", "1"), ("c", "0"))),
    )
    killed = 0
    if certify_t_way_coverage(schema, cases, strength=2).complete:
        killed += 1
    if not certify_t_way_coverage(schema, cases, strength=3).complete:
        killed += 1
    try:
        require_coverage(certify_t_way_coverage(schema, cases, strength=3), min_fraction=1.0)
    except ValueError:
        killed += 1
    try:
        certify_t_way_coverage(
            schema,
            (CoverageCase("bad", (("a", "0"), ("b", "0"), ("c", "9"))),),
            strength=2,
        )
    except ValueError:
        killed += 1
    if killed != 4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-COMBINATORIAL-COVERAGE-ATTACK: PASS killed=4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
