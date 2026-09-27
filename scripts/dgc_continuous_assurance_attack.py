from cwc.governance.continuous_assurance import *


def main():
    cats = tuple(MonitoringCategory)
    spec = MonitoringSpec(
        "d" * 64,
        cats,
        tuple((c, 2) for c in cats),
        (MonitoringCategory.COMPLIANCE,),
        0.2,
    )
    killed = 0
    monitor = ContinuousAssuranceMonitor(spec)

    if monitor.evaluate(as_of_tick=0).decision is AssuranceDecision.HOLD:
        killed += 1

    for category in cats:
        monitor.ingest(
            MonitoringObservation(
                category,
                "m",
                0,
                ObservationStatus.PASS,
                0,
                "d" * 64,
                "e" * 64,
                "src",
                category is MonitoringCategory.COMPLIANCE,
            )
        )
    if monitor.evaluate(as_of_tick=3).decision is AssuranceDecision.HOLD:
        killed += 1

    monitor.ingest(
        MonitoringObservation(
            MonitoringCategory.SECURITY,
            "attack",
            3,
            ObservationStatus.FAIL,
            1,
            "d" * 64,
            "f" * 64,
            "src",
        )
    )
    if monitor.evaluate(as_of_tick=3).decision is AssuranceDecision.ROLLBACK:
        killed += 1

    try:
        monitor.ingest(
            MonitoringObservation(
                MonitoringCategory.SECURITY,
                "x",
                3,
                ObservationStatus.PASS,
                0,
                "x" * 64,
                "e" * 64,
                "src",
            )
        )
    except ValueError:
        killed += 1

    if killed != 4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-CONTINUOUS-ASSURANCE-ATTACK: PASS killed=4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
