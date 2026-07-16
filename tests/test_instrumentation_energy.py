"""python -m pytest tests/test_instrumentation_energy.py -v

Trapezoidal-integration correctness is CPU-only (no GPU needed). Real NVML
backend selection and sampling are exercised against the actual local GPU
where pynvml + NVML are available, marked cuda so they can be skipped
elsewhere.
"""

import time

import pytest

from cwc.instrumentation.energy import (
    EnergySampler,
    NVMLPowerSampler,
    NVMLTotalEnergySampler,
    _trapezoidal_joules,
)
from cwc.instrumentation.types import EnergyRecord


def test_trapezoidal_joules_hand_calculated():
    # constant 10W for 2 seconds = 20 joules
    samples = [(0.0, 10.0), (1.0, 10.0), (2.0, 10.0)]
    assert _trapezoidal_joules(samples) == pytest.approx(20.0)


def test_trapezoidal_joules_ramp():
    # power ramps 0W -> 10W linearly over 2s: area of triangle = 0.5*2*10 = 10J
    samples = [(0.0, 0.0), (2.0, 10.0)]
    assert _trapezoidal_joules(samples) == pytest.approx(10.0)


def test_trapezoidal_joules_requires_two_samples():
    assert _trapezoidal_joules([]) == 0.0
    assert _trapezoidal_joules([(0.0, 5.0)]) == 0.0


def test_power_sampler_degrades_cleanly_without_nvml(monkeypatch):
    monkeypatch.setattr("cwc.instrumentation.energy._PYNVML_AVAILABLE", False)
    sampler = NVMLPowerSampler(sample_rate_hz=100.0)
    assert sampler.available is False
    sampler.start()  # must not raise even though unavailable
    record = sampler.stop()
    assert record.available is False
    assert record.confidence == "unavailable"
    assert record.joules == 0.0


def test_total_energy_sampler_degrades_cleanly_without_nvml(monkeypatch):
    monkeypatch.setattr("cwc.instrumentation.energy._PYNVML_AVAILABLE", False)
    sampler = NVMLTotalEnergySampler()
    assert sampler.available is False
    sampler.start()
    assert sampler.stop() is None  # None, not a fabricated zero record


def test_facade_reports_unavailable_when_no_backend_works(monkeypatch):
    monkeypatch.setattr("cwc.instrumentation.energy._PYNVML_AVAILABLE", False)
    sampler = EnergySampler()
    sampler.start()
    assert sampler.active_backend == "unavailable"
    record = sampler.stop()
    assert record.available is False
    assert record.method == "unavailable"


def test_no_tdp_fallback_exists_in_module():
    """The module docstring correctly *documents* that TDP fallback is
    forbidden (so the string "tdp" legitimately appears there) — what must
    never appear is TDP used in an executable computation. Check the source
    with docstrings/comments stripped instead of a raw substring search.
    """
    import ast
    from pathlib import Path

    import cwc.instrumentation.energy as energy_module

    source = Path(energy_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    code_only_lines = set(range(1, source.count("\n") + 2))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            code_only_lines -= set(range(node.lineno, node.end_lineno + 1))
    lines = source.splitlines()
    executable_source = "\n".join(
        line for i, line in enumerate(lines, start=1)
        if i in code_only_lines and not line.strip().startswith("#")
    )
    assert "tdp" not in executable_source.lower()


@pytest.mark.cuda
def test_power_sampler_reports_real_samples_on_gpu():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this host")
    sampler = NVMLPowerSampler(sample_rate_hz=50.0)
    if not sampler.available:
        pytest.skip("NVML power sampling not available on this host")
    sampler.start()
    time.sleep(0.5)
    record = sampler.stop()
    assert record.available is True
    assert record.sample_count >= 2
    assert record.joules >= 0.0
    # Under 5s window, confidence must be honestly downgraded, never "high".
    assert record.confidence == "low_confidence"


@pytest.mark.cuda
def test_energy_facade_selects_a_real_backend_on_gpu():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this host")
    pytest.importorskip(
        "pynvml", reason="pynvml is not a nanochat dependency; energy graceful-degradation is "
        "covered by test_facade_reports_unavailable_when_no_backend_works instead"
    )
    sampler = EnergySampler(sample_rate_hz=50.0)
    sampler.start()
    time.sleep(0.3)
    record: EnergyRecord = sampler.stop()
    assert sampler.active_backend in ("nvml_total_energy_delta", "nvml_power_sampling")
    assert record.method != "unavailable"
