"""CWC WP-1 smoke test: exercises the full COUNTERS-mode stack (RunMeter,
VRAMMeter, EnergySampler, FlopLedger, RoutingCounters, Writer, manifest) on a
tiny synthetic workload for the requested device, and OFF mode as a no-op
control. Prints PASS/FAIL; exits non-zero on failure.

    python scripts/instrumentation_smoke.py --device cpu
    python scripts/instrumentation_smoke.py --device cuda
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import torch

from cwc.instrumentation.config import InstrumentationConfig, InstrumentationMode
from cwc.instrumentation.energy import EnergySampler
from cwc.instrumentation.event_buffer import EventPool
from cwc.instrumentation.flops import FlopLedger
from cwc.instrumentation.manifest import build_manifest
from cwc.instrumentation.noop import NullEnergySampler, NullRunMeter, NullVRAMMeter
from cwc.instrumentation.routing import RoutingCounters
from cwc.instrumentation.run_meter import RunMeter
from cwc.instrumentation.vram import VRAMMeter
from cwc.instrumentation.writer import InstrumentationWriter


def _workload(device: str):
    x = torch.randn(64, 64, device=device)
    return (x @ x).sum()


def smoke_off(device: str) -> None:
    meter = NullRunMeter()
    for step in range(5):
        with meter.scope("smoke_step", step=step):
            _workload(device)
    meter.close()
    print("OFF: no-op scope executed 5 times, no errors")


def smoke_counters(device: str, output_dir: Path) -> None:
    config = InstrumentationConfig(mode=InstrumentationMode.COUNTERS, output_dir=output_dir)
    pool = EventPool(size=16) if device == "cuda" else None
    if pool is not None:
        pool.warm_up()
    meter = RunMeter(event_pool=pool, enable_cuda_events=device == "cuda")
    vram_meter = VRAMMeter(device=device) if device == "cuda" else NullVRAMMeter()
    energy_sampler = EnergySampler() if device == "cuda" else NullEnergySampler()
    flop_ledger = FlopLedger()
    routing_counters = RoutingCounters()
    writer = InstrumentationWriter(output_dir)

    energy_sampler.start()
    for step in range(5):
        with meter.scope("smoke_step", step=step, tokens=64 * 64):
            _workload(device)
        flop_ledger.add_dense_linear(f"step{step}", tokens=64, d_in=64, d_out=64)
        routing_counters.record(step=step, active_tokens=64, active_blocks=1, active_experts=1, active_parameters=4096)
        writer.write_metric({"step": step})
    records = meter.resolve()
    meter.close()
    energy_record = energy_sampler.stop()

    manifest = build_manifest(
        run_id="smoke", created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        repo_root=Path(__file__).resolve().parents[1], command_line=sys.argv,
        resolved_config={"mode": config.mode.value}, seed=0,
    )
    writer.write_manifest(manifest)
    writer.write_summary(
        {
            "schema_version": "1.0.0",
            "run": {"run_id": "smoke"},
            "environment": {},
            "model": {},
            "workload": {},
            "instrumentation": {"mode": "counters"},
            "latency": {"resolved_count": len(records)},
            "throughput": {},
            "vram": {"available": vram_meter.available if hasattr(vram_meter, "available") else False},
            "flops": flop_ledger.to_dict(),
            "energy": {"available": energy_record.available, "joules": energy_record.joules},
            "routing": {"step_count": routing_counters.snapshot().step_count},
            "validity": {
                "environment_match": True, "warmup_complete": True, "overhead_gate_passed": None,
                "energy_available": energy_record.available, "energy_confidence": energy_record.confidence,
                "profiler_disabled_for_claim_run": True, "trace_disabled_for_claim_run": True,
                "claimable": False, "reasons": ["smoke test, not a claim run"],
            },
        }
    )
    writer.close()
    checksums = writer.compute_checksums()
    assert len(records) == 5, f"expected 5 resolved records, got {len(records)}"
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "summary.json").exists()
    assert checksums.exists()
    print(f"COUNTERS ({device}): 5 steps resolved, evidence bundle written to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        print(f"SMOKE SKIP: --device cuda requested but CUDA is not available on this host")
        return

    output_dir = Path("artifacts/instrumentation") / f"smoke-{args.device}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    try:
        smoke_off(args.device)
        smoke_counters(args.device, output_dir)
    except Exception as exc:
        print(f"SMOKE FAIL ({args.device}): {exc}")
        raise SystemExit(1) from exc
    finally:
        if output_dir.exists():
            shutil.rmtree(output_dir)

    print(f"SMOKE PASS ({args.device})")


if __name__ == "__main__":
    main()
