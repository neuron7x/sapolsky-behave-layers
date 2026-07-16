"""python -m pytest tests/test_instrumentation_cuda_events.py -v -m cuda

Skipped entirely if CUDA is unavailable (Act 8.2). These tests exercise the
event pool and deferred-resolution clock against the real local GPU; they do
not depend on nanochat's pinned torch==2.9.1 specifically (torch.cuda.Event's
API has been stable across 2.x), but any numeric latency reported here is
still an environment-mismatch-flagged number end to end (see ADR-0001).
"""

import pytest

torch = pytest.importorskip("torch")

pytestmark = [
    pytest.mark.cuda,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available on this host"),
]

from cwc.instrumentation.clock import open_window, resolve_windows
from cwc.instrumentation.event_buffer import EventPool
from cwc.instrumentation.run_meter import RunMeter


def test_event_pool_warms_up_and_acquires():
    pool = EventPool(size=4)
    assert not pool.warmed_up
    pool.warm_up()
    assert pool.warmed_up
    assert pool.available_count == 4
    pair = pool.acquire()
    assert pair is not None
    assert pool.available_count == 3


def test_event_pool_overflow_is_counted_not_raised():
    pool = EventPool(size=1)
    pool.warm_up()
    first = pool.acquire()
    assert first is not None
    second = pool.acquire()
    assert second is None
    assert pool.dropped_event_pairs == 1


def test_event_pool_release_returns_pair():
    pool = EventPool(size=1)
    pool.warm_up()
    pair = pool.acquire()
    assert pool.available_count == 0
    pool.release(pair)
    assert pool.available_count == 1


def test_cuda_event_elapsed_time_is_positive():
    pool = EventPool(size=2)
    pool.warm_up()
    window = open_window(pool, device_index=0)
    assert window is not None
    window.mark_start()
    x = torch.randn(2048, 2048, device="cuda")
    for _ in range(20):
        x = x @ x.abs().clamp(max=1.0)
    window.mark_end()
    elapsed_ms = resolve_windows([window], pool)
    assert len(elapsed_ms) == 1
    assert elapsed_ms[0] > 0.0
    # event pair must be returned to the pool after resolution
    assert pool.available_count == 2


def test_resolve_windows_rejects_mixed_devices():
    pool = EventPool(size=2)
    pool.warm_up()
    window_a = open_window(pool, device_index=0)
    window_b = open_window(pool, device_index=0)
    assert window_a is not None and window_b is not None
    window_b.device_index = 1  # simulate a second device without one being present
    with pytest.raises(ValueError, match="cannot mix CUDA events from different devices"):
        resolve_windows([window_a, window_b], pool)


def test_no_synchronize_between_start_and_end(monkeypatch):
    """Deferred synchronization: torch.cuda.synchronize must not be called
    while a window is open, only inside resolve_windows.
    """
    calls = []
    real_sync = torch.cuda.synchronize

    def counting_sync(*args, **kwargs):
        calls.append((args, kwargs))
        return real_sync(*args, **kwargs)

    monkeypatch.setattr(torch.cuda, "synchronize", counting_sync)
    pool = EventPool(size=1)
    pool.warm_up()
    window = open_window(pool, device_index=0)
    assert window is not None
    window.mark_start()
    assert calls == []  # no sync during mark_start
    window.mark_end()
    assert calls == []  # no sync during mark_end
    resolve_windows([window], pool)
    assert len(calls) == 1  # exactly one sync, inside resolve


def test_run_meter_scope_records_gpu_and_e2e_latency():
    pool = EventPool(size=4)
    pool.warm_up()
    meter = RunMeter(event_pool=pool, device_index=0, enable_cuda_events=True)
    with meter.scope("train_step", step=0, tokens=128):
        x = torch.randn(1024, 1024, device="cuda")
        x = x @ x
    records = meter.resolve()
    assert len(records) == 1
    record = records[0]
    assert record.status == "ok"
    assert record.end_to_end_ms > 0.0
    assert record.gpu_kernel_ms >= 0.0
    assert record.tokens == 128


def test_run_meter_propagates_exceptions_and_tags_error_status():
    pool = EventPool(size=2)
    pool.warm_up()
    meter = RunMeter(event_pool=pool, device_index=0, enable_cuda_events=True)
    with pytest.raises(RuntimeError, match="boom"), meter.scope("train_step", step=1):
        raise RuntimeError("boom")
    records = meter.flush()
    assert len(records) == 1
    assert records[0].status == "error"
    assert records[0].error_type == "RuntimeError"


def test_run_meter_close_is_idempotent():
    pool = EventPool(size=2)
    pool.warm_up()
    meter = RunMeter(event_pool=pool, device_index=0, enable_cuda_events=True)
    with meter.scope("train_step", step=0):
        pass
    meter.close()
    meter.close()  # must not raise or double-resolve
    assert len(meter.records) == 1
