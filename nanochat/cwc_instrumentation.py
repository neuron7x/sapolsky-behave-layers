"""
CWC WP-1 measurement loop: additive telemetry for the Cognitive Wiring Core
falsification substrate (research/EXPERIMENTAL_SUBSTRATE_NANOCHAT.md in the
cognitive-weave-kernel repo, CWC-EXPSUB-NANOCHAT-001).

This module does not change nanochat's training numerics. It extends nanochat's
existing measurement loop (val_bpb, CORE, VRAM via torch.cuda.max_memory_allocated,
MFU via GPT.estimate_flops) with the two axes CWC needs and nanochat does not yet
report: energy and activated-vs-dense compute.

Design constraint driving both classes below: measurement overhead must not
distort the latency signal being measured (see ADR discussion in the CWC repo).
Two established patterns are used instead of `torch.profiler` on the hot path:

1. Energy: a background thread polls the driver's power counter (NVML) at a
   coarse interval and integrates power over time. This is the approach used by
   MLCommons Power (SPEC/MLPerf) methodology. It touches no tensors and adds no
   per-op hooks, so it cannot perturb step latency.
2. Activated compute: a plain counter fed by whichever routing/expert-dispatch
   code exists (WP-3+). Before routing exists, `record_dense_step` reports
   activated == dense honestly (there is nothing to route yet). This mirrors
   nanochat's own `GPT.estimate_flops`: a static analytical formula, not a
   runtime profiler trace. `torch.profiler` remains appropriate for periodic,
   offline calibration of these numbers (e.g. a `--profile-every` diagnostic
   run), never for per-step accounting.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

try:
    import pynvml
    _PYNVML_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised only when pynvml is absent
    pynvml = None
    _PYNVML_IMPORT_ERROR = exc


class EnergySampler:
    """Background NVML power-draw sampler. Integrates watts over time to joules.

    Runs in a daemon thread at a coarse poll interval so it cannot meaningfully
    perturb the training step it is measuring alongside. If NVML is unavailable
    (no pynvml install, no NVIDIA GPU, or driver too old) it degrades to
    reporting zero joules rather than raising, since energy is an optional axis
    on top of the existing FLOPs/VRAM/latency telemetry, not a hard requirement.
    """

    def __init__(self, device_index: int = 0, poll_interval_s: float = 0.1) -> None:
        self.device_index = device_index
        self.poll_interval_s = poll_interval_s
        self._joules = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._handle = None
        self.available = False
        if pynvml is not None:
            try:
                pynvml.nvmlInit()
                self._handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
                self.available = True
            except Exception:
                self.available = False

    def _poll_loop(self) -> None:
        last_t = time.monotonic()
        while not self._stop_event.is_set():
            now = time.monotonic()
            dt = now - last_t
            last_t = now
            try:
                milliwatts = pynvml.nvmlDeviceGetPowerUsage(self._handle)
            except Exception:
                self._stop_event.wait(self.poll_interval_s)
                continue
            watts = milliwatts / 1000.0
            with self._lock:
                self._joules += watts * dt
            self._stop_event.wait(self.poll_interval_s)

    def start(self) -> None:
        if not self.available or self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=self.poll_interval_s * 5)
        self._thread = None

    def joules_since_start(self) -> float:
        with self._lock:
            return self._joules

    def reset(self) -> None:
        with self._lock:
            self._joules = 0.0


@dataclass
class ActivatedComputeCounter:
    """Tracks activated vs dense-equivalent FLOPs across steps.

    Pre-routing (no WP-3 yet), `record_dense_step` is the only call site and
    `activated_fraction` is honestly 1.0 — the whole dense model fires for every
    token, there is no sparsity to report. Once WP-3 introduces routing,
    `record_routed_step` is the call site instead, and this same object reports
    the true activated fraction without any change to callers that only read
    `activated_fraction` / `total_activated_flops`.
    """

    total_dense_flops: float = 0.0
    total_activated_flops: float = 0.0
    steps_recorded: int = 0

    def record_dense_step(self, dense_flops_this_step: float) -> None:
        self.total_dense_flops += dense_flops_this_step
        self.total_activated_flops += dense_flops_this_step
        self.steps_recorded += 1

    def record_routed_step(self, activated_flops_this_step: float, dense_equivalent_flops_this_step: float) -> None:
        if activated_flops_this_step > dense_equivalent_flops_this_step:
            raise ValueError(
                "activated_flops_this_step cannot exceed dense_equivalent_flops_this_step "
                "(routing only skips compute, it does not add unaccounted compute)"
            )
        self.total_dense_flops += dense_equivalent_flops_this_step
        self.total_activated_flops += activated_flops_this_step
        self.steps_recorded += 1

    @property
    def activated_fraction(self) -> float:
        if self.total_dense_flops == 0.0:
            return 1.0
        return self.total_activated_flops / self.total_dense_flops


@dataclass
class RoutingTelemetry:
    """Placeholder logging contract for WP-3 (not populated until routing exists).

    Declared now so WP-3 extends this schema instead of inventing a parallel one —
    the determinism the user asked for applies to the logging contract too, not
    only to the value-function gate in the CWC repo.
    """

    route_entropy_mean: float | None = None
    expert_utilization: list[float] = field(default_factory=list)
    overflow_count: int = 0
    fallback_used: bool = False
