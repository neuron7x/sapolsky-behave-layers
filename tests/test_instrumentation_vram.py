"""python -m pytest tests/test_instrumentation_vram.py -v"""

import pytest

from cwc.instrumentation.vram import VRAMMeter


def test_vram_meter_unavailable_reports_none_on_cpu_device_string(monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    meter = VRAMMeter(device="cuda")
    assert meter.snapshot() is None
    meter.reset_peak()  # must not raise even though unavailable


@pytest.mark.cuda
def test_vram_meter_reports_real_allocation():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this host")
    meter = VRAMMeter(device="cuda")
    meter.reset_peak()
    tensor = torch.zeros(1024, 1024, device="cuda")  # 4 MiB fp32
    record = meter.snapshot(scope_name="alloc_test")
    del tensor
    assert record is not None
    assert record.peak_allocated_bytes >= 4 * 1024 * 1024
    assert record.device == "cuda"
    assert record.scope_name == "alloc_test"


@pytest.mark.cuda
def test_vram_meter_never_calls_empty_cache(monkeypatch):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this host")
    calls = []
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: calls.append(1))
    meter = VRAMMeter(device="cuda")
    meter.reset_peak()
    meter.snapshot()
    meter.windowed_snapshot()
    assert calls == []
