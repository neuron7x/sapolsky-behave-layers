"""L0 measurement substrate — the instrument the whole programme trusts.

WHAT
    A resource meter for a training/inference run: FLOPs (`flops`), VRAM (`vram`),
    latency (`clock`), energy (`energy`), routing statistics (`routing`), plus the
    record types (`types`), configuration (`config`), a null/no-op implementation
    (`noop`), aggregation (`stats`), a run meter (`run_meter`), an audit path
    (`audit`), and serialization (`writer`, `manifest`).

WHY it exists first (design argument)
    Every downstream claim about "cheaper" or "faster" is only as trustworthy as the
    number that measured it. So the measurement layer is built and validated (L0)
    BEFORE any mechanism claim (L1+): 207 tests, 99.46% branch coverage, 12/12 mutation
    kills. Two disciplines are enforced package-wide and are the reason to trust it:

      - **Honest absence over fabricated precision.** An unmeasurable quantity is
        reported as unavailable, never faked. `energy` forbids TDP*time and returns
        0 J only attached to `available=False`; `flops` keeps logical and
        executed-estimate FLOPs as separate numbers and refuses the wrong `F_MoE`
        formula; unsupported operations are marked, not guessed.
      - **Mathematical neutrality (Gate B).** `InstrumentationMode.OFF` is a true no-op
        (`noop`): turning measurement on must not change the computation being measured.

    Units are not optional: every field name in `types` carries its unit suffix
    (`_ns`, `_bytes`, `_joules`, `_flops`, ...) so a bare `energy`/`mem` can never hide
    an ambiguous quantity.

NON-CLAIM (anti-pseudo)
    On this hardware (RTX 3050) energy is `INSTRUMENT_INVALID` and is excluded from
    every claim. WP-1 implements no router or MoE; `routing` and the MoE FLOP interface
    are *measurement-ready contracts* exercised with synthetic values, not evidence of
    a real router.
"""

from .config import InstrumentationConfig, InstrumentationMode
from .noop import (
    NullEnergySampler,
    NullFlopLedger,
    NullRoutingCounters,
    NullRunMeter,
    NullVRAMMeter,
    NullWriter,
)
from .types import (
    DeviceManifest,
    EnergyRecord,
    EnvironmentManifest,
    FlopRecord,
    InstrumentationSummary,
    LatencyRecord,
    OverheadResult,
    RoutingAggregate,
    RunIdentity,
    VRAMRecord,
)

__all__ = [
    "DeviceManifest",
    "EnergyRecord",
    "EnvironmentManifest",
    "FlopRecord",
    "InstrumentationConfig",
    "InstrumentationMode",
    "InstrumentationSummary",
    "LatencyRecord",
    "NullEnergySampler",
    "NullFlopLedger",
    "NullRoutingCounters",
    "NullRunMeter",
    "NullVRAMMeter",
    "NullWriter",
    "OverheadResult",
    "RoutingAggregate",
    "RunIdentity",
    "VRAMRecord",
]
