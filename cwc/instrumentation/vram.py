"""torch.cuda allocator peak-stats reporting (Act 4.7). Never calls
empty_cache() — that would perturb the allocator state being measured.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .types import VRAMRecord

if TYPE_CHECKING:
    import torch


class VRAMMeter:
    def __init__(self, device: torch.device | str | int = "cuda") -> None:
        self.device = device

    @property
    def available(self) -> bool:
        import torch

        return bool(torch.cuda.is_available())

    def reset_peak(self) -> None:
        if not self.available:
            return
        import torch

        torch.cuda.reset_peak_memory_stats(self.device)

    def snapshot(self, *, scope_name: str = "") -> VRAMRecord | None:
        if not self.available:
            return None
        import torch

        return VRAMRecord(
            scope_name=scope_name,
            device=str(self.device),
            start_allocated_bytes=int(torch.cuda.memory_allocated(self.device)),
            start_reserved_bytes=int(torch.cuda.memory_reserved(self.device)),
            peak_allocated_bytes=int(torch.cuda.max_memory_allocated(self.device)),
            peak_reserved_bytes=int(torch.cuda.max_memory_reserved(self.device)),
            end_allocated_bytes=int(torch.cuda.memory_allocated(self.device)),
            end_reserved_bytes=int(torch.cuda.memory_reserved(self.device)),
        )

    def windowed_snapshot(self, *, scope_name: str = "") -> VRAMRecord | None:
        """Call reset_peak() before the scope, this after — start_* fields
        reflect allocator state at reset time is not tracked here, so callers
        that need a true start/end delta should snapshot twice and construct
        their own VRAMRecord; this convenience method reports current +
        peak-since-last-reset only.
        """
        return self.snapshot(scope_name=scope_name)
