"""python -m pytest tests/test_instrumentation_energy_nvml.py -v

Drives the real NVML backend logic in cwc/instrumentation/energy.py by
injecting a fake `pynvml` module — no physical GPU/NVML needed. This covers
the total-energy-delta and power-sampling code paths that the hardware-gated
tests in test_instrumentation_energy.py can only reach on a machine where NVML
is actually present, so coverage is deterministic and CI-portable.
"""

import time

import pytest

import cwc.instrumentation.energy as energy_mod
from cwc.instrumentation.energy import EnergySampler, NVMLPowerSampler, NVMLTotalEnergySampler


class _FakeNVML:
    """Minimal fake of the pynvml surface energy.py touches."""

    def __init__(self, *, power_mw=50_000, total_energy_supported=True, energy_mj_series=None):
        self._power_mw = power_mw
        self._total_energy_supported = total_energy_supported
        self._energy_mj_series = list(energy_mj_series) if energy_mj_series else [1000, 2500]
        self._energy_idx = 0
        self.init_called = 0

    def nvmlInit(self):
        self.init_called += 1

    def nvmlDeviceGetHandleByIndex(self, index):
        return f"handle-{index}"

    def nvmlDeviceGetPowerUsage(self, handle):
        return self._power_mw

    def nvmlDeviceGetTotalEnergyConsumption(self, handle):
        if not self._total_energy_supported:
            raise RuntimeError("NVML_ERROR_NOT_SUPPORTED")
        value = self._energy_mj_series[min(self._energy_idx, len(self._energy_mj_series) - 1)]
        self._energy_idx += 1
        return value


@pytest.fixture
def fake_nvml(monkeypatch):
    fake = _FakeNVML()
    monkeypatch.setattr(energy_mod, "pynvml", fake)
    monkeypatch.setattr(energy_mod, "_PYNVML_AVAILABLE", True)
    return fake


def test_total_energy_backend_reports_delta(fake_nvml):
    # series[0] is consumed by the __init__ capability probe; start()/stop()
    # then read 1000 and 6000 -> 5000 mJ delta = 5.0 J
    fake_nvml._energy_mj_series = [0, 1000, 6000]
    sampler = NVMLTotalEnergySampler()
    assert sampler.available is True
    sampler.start()
    record = sampler.stop()
    assert record is not None
    assert record.method == "nvml_total_energy_delta"
    assert record.joules == pytest.approx(5.0)
    assert record.available is True


def test_total_energy_backend_unsupported_device_is_unavailable(monkeypatch):
    fake = _FakeNVML(total_energy_supported=False)
    monkeypatch.setattr(energy_mod, "pynvml", fake)
    monkeypatch.setattr(energy_mod, "_PYNVML_AVAILABLE", True)
    sampler = NVMLTotalEnergySampler()
    assert sampler.available is False  # capability probe failed
    assert sampler.stop() is None      # None, not a fabricated record


def test_total_energy_delta_never_negative(fake_nvml):
    # counter appears to go backwards (driver reset) -> clamp to 0, not negative
    # (series[0] = probe, then start reads 6000, stop reads 1000)
    fake_nvml._energy_mj_series = [0, 6000, 1000]
    sampler = NVMLTotalEnergySampler()
    sampler.start()
    record = sampler.stop()
    assert record is not None
    assert record.joules >= 0.0


def test_power_sampler_collects_real_samples(fake_nvml):
    sampler = NVMLPowerSampler(sample_rate_hz=200.0)  # 5ms interval
    assert sampler.available is True
    sampler.start()
    time.sleep(0.08)  # ~16 samples
    record = sampler.stop()
    assert record.available is True
    assert record.sample_count >= 2
    assert record.method == "nvml_power_sampling"
    # 50W constant over the window
    assert record.average_watts == pytest.approx(50.0, abs=1.0)
    assert record.joules > 0.0
    # under 5s -> confidence downgraded, never "high"
    assert record.confidence == "low_confidence"
    assert sampler.median_sampling_interval_sec > 0.0


def test_power_sampler_counts_missed_samples(monkeypatch):
    fake = _FakeNVML()
    calls = {"n": 0}
    real_power = fake.nvmlDeviceGetPowerUsage

    def flaky_power(handle):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise RuntimeError("transient NVML read error")
        return real_power(handle)

    fake.nvmlDeviceGetPowerUsage = flaky_power
    monkeypatch.setattr(energy_mod, "pynvml", fake)
    monkeypatch.setattr(energy_mod, "_PYNVML_AVAILABLE", True)
    sampler = NVMLPowerSampler(sample_rate_hz=200.0)
    sampler.start()
    time.sleep(0.08)
    sampler.stop()
    assert sampler.missed_samples > 0


def test_power_sampler_single_sample_is_low_confidence(fake_nvml):
    sampler = NVMLPowerSampler(sample_rate_hz=1.0)  # 1s interval: at most 1 sample in a short window
    sampler.start()
    time.sleep(0.02)
    record = sampler.stop()
    # 0 or 1 samples -> cannot integrate -> low_confidence, joules 0
    assert record.confidence in ("low_confidence", "unavailable")
    assert record.joules == 0.0


def test_facade_prefers_total_energy_backend(fake_nvml):
    # series[0] = probe, then start reads 0, stop reads 3000 -> 3.0 J
    fake_nvml._energy_mj_series = [0, 0, 3000]
    sampler = EnergySampler()
    sampler.start()
    assert sampler.active_backend == "nvml_total_energy_delta"
    record = sampler.stop()
    assert record.method == "nvml_total_energy_delta"
    assert record.joules == pytest.approx(3.0)


def test_facade_falls_back_to_power_sampling(monkeypatch):
    # total-energy unsupported -> facade must select power sampling
    fake = _FakeNVML(total_energy_supported=False)
    monkeypatch.setattr(energy_mod, "pynvml", fake)
    monkeypatch.setattr(energy_mod, "_PYNVML_AVAILABLE", True)
    sampler = EnergySampler(sample_rate_hz=200.0)
    sampler.start()
    assert sampler.active_backend == "nvml_power_sampling"
    time.sleep(0.05)
    record = sampler.stop()
    assert record.method == "nvml_power_sampling"


def test_power_sampler_high_confidence_path(monkeypatch, fake_nvml):
    # Force a >=5s duration without actually sleeping: seed the sample buffer
    # directly, then call stop() with the thread already gone.
    sampler = NVMLPowerSampler(sample_rate_hz=10.0)
    sampler._samples = [(0.0, 50.0), (6.0, 50.0)]  # 6s span, 50W
    record = sampler.stop()
    assert record.confidence == "high"
    assert record.duration_sec == pytest.approx(6.0)
    assert record.joules == pytest.approx(300.0)  # 50W * 6s


def test_total_energy_high_confidence_path(monkeypatch, fake_nvml):
    # series[0] = probe, start reads 0, stop reads 300000 mJ = 300 J
    fake_nvml._energy_mj_series = [0, 0, 300_000]
    sampler = NVMLTotalEnergySampler()
    sampler.start()
    sampler._start_monotonic = time.monotonic() - 6.0  # pretend 6s elapsed
    record = sampler.stop()
    assert record is not None
    assert record.confidence == "high"
