import pytest
from cwc.governance.continuous_assurance import *

CATS = tuple(MonitoringCategory)


def spec(**overrides):
    base = dict(
        deployment_digest="d" * 64,
        required_categories=CATS,
        max_age_ticks=tuple((c, 10) for c in CATS),
        human_validation_required=(MonitoringCategory.HUMAN_FACTORS, MonitoringCategory.COMPLIANCE),
        max_warn_risk_sum=0.5,
    )
    base.update(overrides)
    return MonitoringSpec(**base)


def obs(cat, status=ObservationStatus.PASS, tick=1, risk=0, human=False, metric="m"):
    return MonitoringObservation(cat, metric, tick, status, risk, "d" * 64, "e" * 64, "src", human)


def fill(monitor, tick=1):
    for category in CATS:
        monitor.ingest(obs(category, tick=tick, human=category in (MonitoringCategory.HUMAN_FACTORS, MonitoringCategory.COMPLIANCE)))


def test_all_fresh_pass_allows_continue():
    monitor = ContinuousAssuranceMonitor(spec())
    fill(monitor)
    assert monitor.evaluate(as_of_tick=5).decision is AssuranceDecision.CONTINUE


def test_missing_category_holds_fail_closed():
    monitor = ContinuousAssuranceMonitor(spec())
    for category in CATS[:-1]:
        monitor.ingest(obs(category, human=category in (MonitoringCategory.HUMAN_FACTORS, MonitoringCategory.COMPLIANCE)))
    cert = monitor.evaluate(as_of_tick=2)
    assert cert.decision is AssuranceDecision.HOLD
    assert any(x.startswith("MISSING") for x in cert.reasons)


def test_stale_category_holds():
    monitor = ContinuousAssuranceMonitor(spec())
    fill(monitor, tick=1)
    assert monitor.evaluate(as_of_tick=12).decision is AssuranceDecision.HOLD


def test_any_fail_rolls_back():
    monitor = ContinuousAssuranceMonitor(spec())
    fill(monitor)
    monitor.ingest(obs(MonitoringCategory.SECURITY, status=ObservationStatus.FAIL, tick=2, risk=1, metric="attack"))
    assert monitor.evaluate(as_of_tick=3).decision is AssuranceDecision.ROLLBACK


def test_human_validation_required():
    monitor = ContinuousAssuranceMonitor(spec())
    for category in CATS:
        monitor.ingest(obs(category, human=False))
    cert = monitor.evaluate(as_of_tick=2)
    assert cert.decision is AssuranceDecision.HOLD
    assert any("HUMAN_VALIDATION_MISSING" in x for x in cert.reasons)


def test_warning_risk_accumulates_and_holds_over_threshold():
    monitor = ContinuousAssuranceMonitor(spec())
    fill(monitor)
    monitor.ingest(obs(MonitoringCategory.OPERATIONAL, status=ObservationStatus.WARN, tick=2, risk=0.3, metric="latency"))
    monitor.ingest(obs(MonitoringCategory.SECURITY, status=ObservationStatus.WARN, tick=2, risk=0.3, metric="abuse"))
    assert monitor.evaluate(as_of_tick=3).decision is AssuranceDecision.HOLD


def test_wrong_deployment_and_conflicting_duplicate_rejected():
    monitor = ContinuousAssuranceMonitor(spec())
    bad = MonitoringObservation(MonitoringCategory.SECURITY, "m", 1, ObservationStatus.PASS, 0, "x" * 64, "e" * 64, "src")
    with pytest.raises(ValueError, match="deployment digest mismatch"):
        monitor.ingest(bad)
    good = obs(MonitoringCategory.SECURITY)
    monitor.ingest(good)
    monitor.ingest(good)
    conflict = MonitoringObservation(MonitoringCategory.SECURITY, "m", 1, ObservationStatus.FAIL, 1, "d" * 64, "e" * 64, "src")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        monitor.ingest(conflict)
