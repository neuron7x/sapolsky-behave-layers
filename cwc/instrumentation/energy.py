"""GPU energy measurement (Act 4.9). Backend hierarchy, strictly in this
order, each one tried only if the previous is unavailable:

1. NVML total-energy-consumption delta (most accurate where supported).
2. NVML power sampling + trapezoidal integration (background thread).
3. External wall-meter import/calibration (interface only; not auto-invoked —
   no such hardware exists in this environment, so implementing an automatic
   fallback to it here would be inventing data. See ExternalWallMeterAdapter).
4. status = "unavailable".

Forbidden anywhere in this module: TDP fallback, TDP x utilization, fabricated
watts, or reporting 0 as if it were a real measurement of an unmeasured
window (Act 4.9). Zero joules is only ever returned attached to
available=False / confidence="unavailable".
"""

from __future__ import annotations

import itertools
import statistics
import threading
import time
from dataclasses import dataclass, field

from .types import EnergyRecord

try:
    import pynvml

    _PYNVML_AVAILABLE = True
except ImportError:
    pynvml = None
    _PYNVML_AVAILABLE = False


class ExternalWallMeterAdapter:
    """Interface for a physically calibrated external power meter. Not wired
    to any automatic fallback: no such device is present in this environment.
    A future integration provides `read_joules(start_s, end_s) -> float` and
    is selected explicitly by the caller, never silently substituted for NVML.
    """

    def read_joules(self, start_s: float, end_s: float) -> float:
        raise NotImplementedError(
            "no external wall meter is configured; this adapter must be "
            "supplied and calibrated explicitly, it is never an automatic fallback"
        )


def _trapezoidal_joules(samples: list[tuple[float, float]]) -> float:
    """samples: list of (timestamp_s, watts), using actual timestamps, not a
    nominal period (Act 4.9 energy-validity requirement).
    """
    if len(samples) < 2:
        return 0.0
    total = 0.0
    for (t0, w0), (t1, w1) in itertools.pairwise(samples):
        dt = max(0.0, t1 - t0)
        total += 0.5 * (w0 + w1) * dt
    return total


class NVMLPowerSampler:
    """Backend 2: background NVML power-draw polling thread. Started before
    warm-up, monotonic timestamps, samples buffered in memory (no per-sample
    disk write during the measurement window), sampling target default 10 Hz.
    """

    def __init__(self, device_index: int = 0, sample_rate_hz: float = 10.0) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be > 0")
        self.device_index = device_index
        self.sample_rate_hz = sample_rate_hz
        self._interval_s = 1.0 / sample_rate_hz
        self._samples: list[tuple[float, float]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._handle = None
        self._missed_samples = 0
        self.available = False
        if _PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self._handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
                self.available = True
            except Exception:
                self.available = False

    def start(self) -> None:
        if not self.available or self._thread is not None:
            return
        self._samples.clear()
        self._missed_samples = 0
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            try:
                milliwatts = pynvml.nvmlDeviceGetPowerUsage(self._handle)
                self._samples.append((now, milliwatts / 1000.0))
            except Exception:
                self._missed_samples += 1
            self._stop_event.wait(self._interval_s)

    def stop(self) -> EnergyRecord:
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=max(1.0, self._interval_s * 5))
            self._thread = None
        if not self.available or len(self._samples) < 2:
            # Fewer than two samples cannot be trapezoidally integrated: the
            # measurement window is UNMEASURED. Per this module's contract
            # (see the header: "Zero joules is only ever returned attached to
            # available=False / confidence=unavailable"), an unmeasured window
            # must NOT report joules=0.0 with available=True — that fabricates a
            # 0 J reading for a window we never measured. So a 0- or 1-sample
            # stop is available=False / confidence=unavailable. sample_count is
            # preserved so a caller can still see that one probe landed.
            return EnergyRecord(
                available=False,
                method="nvml_power_sampling",
                sample_count=len(self._samples),
                duration_sec=0.0,
                joules=0.0,
                average_watts=0.0,
                confidence="unavailable",
            )
        duration_sec = self._samples[-1][0] - self._samples[0][0]
        joules = _trapezoidal_joules(self._samples)
        average_watts = joules / duration_sec if duration_sec > 0 else 0.0
        confidence = "high" if duration_sec >= 5.0 else "low_confidence"
        return EnergyRecord(
            available=True,
            method="nvml_power_sampling",
            sample_count=len(self._samples),
            duration_sec=duration_sec,
            joules=joules,
            average_watts=average_watts,
            confidence=confidence,
        )

    @property
    def missed_samples(self) -> int:
        return self._missed_samples

    @property
    def median_sampling_interval_sec(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        intervals = [b[0] - a[0] for a, b in itertools.pairwise(self._samples)]
        return statistics.median(intervals)


class NVMLTotalEnergySampler:
    """Backend 1: NVML's own energy-consumption counter (millijoules since
    driver load), used as a start/end delta when the device supports it.
    """

    def __init__(self, device_index: int = 0) -> None:
        self.device_index = device_index
        self._handle = None
        self._start_mj: int | None = None
        self._start_monotonic: float | None = None
        self.available = False
        if _PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
                pynvml.nvmlDeviceGetTotalEnergyConsumption(handle)  # capability probe
                self._handle = handle
                self.available = True
            except Exception:
                self.available = False

    def start(self) -> None:
        if not self.available:
            return
        self._start_mj = pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle)
        self._start_monotonic = time.monotonic()

    def stop(self) -> EnergyRecord | None:
        """Returns None (not a record) if this backend is not usable, so the
        caller can fall through to backend 2 rather than reporting a fake zero.
        """
        if not self.available or self._start_mj is None or self._start_monotonic is None:
            return None
        end_mj = pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle)
        duration_sec = time.monotonic() - self._start_monotonic
        joules = max(0, end_mj - self._start_mj) / 1000.0
        average_watts = joules / duration_sec if duration_sec > 0 else 0.0
        confidence = "high" if duration_sec >= 5.0 else "low_confidence"
        return EnergyRecord(
            available=True,
            method="nvml_total_energy_delta",
            sample_count=2,
            duration_sec=duration_sec,
            joules=joules,
            average_watts=average_watts,
            confidence=confidence,
        )


@dataclass
class EnergySampler:
    """Top-level facade implementing the full backend hierarchy (Act 4.9).
    Selects the best available backend at start() time and never falls back
    to TDP or a fabricated number.
    """

    device_index: int = 0
    sample_rate_hz: float = 10.0
    _total_energy_backend: NVMLTotalEnergySampler | None = field(default=None, init=False)
    _power_sampling_backend: NVMLPowerSampler | None = field(default=None, init=False)
    _active_backend: str = field(default="unavailable", init=False)

    def start(self) -> None:
        total_energy = NVMLTotalEnergySampler(self.device_index)
        if total_energy.available:
            total_energy.start()
            self._total_energy_backend = total_energy
            self._active_backend = "nvml_total_energy_delta"
            return
        power_sampling = NVMLPowerSampler(self.device_index, self.sample_rate_hz)
        if power_sampling.available:
            power_sampling.start()
            self._power_sampling_backend = power_sampling
            self._active_backend = "nvml_power_sampling"
            return
        self._active_backend = "unavailable"

    def stop(self) -> EnergyRecord:
        if self._total_energy_backend is not None:
            record = self._total_energy_backend.stop()
            if record is not None:
                return record
        if self._power_sampling_backend is not None:
            return self._power_sampling_backend.stop()
        return EnergyRecord(
            available=False,
            method="unavailable",
            sample_count=0,
            duration_sec=0.0,
            joules=0.0,
            average_watts=0.0,
            confidence="unavailable",
        )

    @property
    def active_backend(self) -> str:
        return self._active_backend
