"""python -m pytest tests/test_instrumentation_determinism.py -v

Reproducibility gate: the deterministic layers of the instrumentation must
produce byte-identical output on repeated invocation with the same inputs.
This is what makes an evidence bundle auditable — a layer that varies across
runs (without a recorded seed) is a reproducibility fault.
"""

import json
from pathlib import Path

from cwc.instrumentation.flops import FlopLedger
from cwc.instrumentation.manifest import build_manifest
from cwc.instrumentation.routing import RoutingCounters
from cwc.instrumentation.stats import bootstrap_ci, percentile
from cwc.instrumentation.writer import InstrumentationWriter


def _build_ledger() -> FlopLedger:
    ledger = FlopLedger()
    ledger.add_dense_linear("l0", tokens=128, d_in=768, d_out=768)
    ledger.add_attention("a0", batch=4, seq_len=256, d_model=768, n_head=6, n_kv_head=6, head_dim=128)
    ledger.add_mlp("m0", tokens=1024, d_model=768, d_ff=3072)
    ledger.add_lm_head("h0", tokens=1024, d_model=768, vocab_size=32768)
    return ledger


def test_flop_ledger_to_dict_is_byte_identical():
    a = json.dumps(_build_ledger().to_dict(), sort_keys=True)
    b = json.dumps(_build_ledger().to_dict(), sort_keys=True)
    assert a == b


def test_routing_snapshot_is_byte_identical():
    import dataclasses

    def snap() -> str:
        c = RoutingCounters()
        for step in range(50):
            c.record(
                step=step, active_tokens=step * 3, active_blocks=2,
                active_experts=1, active_parameters=1000,
            )
        return json.dumps(dataclasses.asdict(c.snapshot()), sort_keys=True, default=str)

    assert snap() == snap()


def test_bootstrap_ci_byte_identical_given_seed():
    deltas = [0.01, -0.02, 0.03, 0.005, -0.008, 0.012, 0.0, 0.02]
    a = bootstrap_ci(deltas, resamples=500, seed=1234, confidence=0.95)
    b = bootstrap_ci(deltas, resamples=500, seed=1234, confidence=0.95)
    assert a == b  # same seed -> byte-identical, the reproducibility gate


def test_percentile_is_pure_and_repeatable():
    values = [4.0, 1.0, 9.0, 2.0, 7.0, 3.0]
    for q in (0.0, 0.1, 0.5, 0.9, 1.0):
        assert percentile(values, q) == percentile(values, q)


def test_writer_summary_bytes_identical_for_identical_input(tmp_path: Path):
    payload = {
        "schema_version": "1.0.0",
        "flops": _build_ledger().to_dict(),
        "nested": {"b": 2, "a": 1, "c": [3, 2, 1]},
    }
    w1 = InstrumentationWriter(tmp_path / "r1")
    p1 = w1.write_summary(payload)
    w2 = InstrumentationWriter(tmp_path / "r2")
    p2 = w2.write_summary(payload)
    # sort_keys=True in the writer guarantees a canonical byte layout
    assert p1.read_bytes() == p2.read_bytes()


def test_writer_checksums_stable_across_runs(tmp_path: Path):
    def make(dirname: str) -> str:
        w = InstrumentationWriter(tmp_path / dirname)
        w.write_metric({"step": 0, "value": 1.5})
        w.write_metric({"step": 1, "value": 2.5})
        w.write_summary({"schema_version": "1.0.0", "ok": True})
        w.close()
        w.compute_checksums()
        # strip the run-dir-relative path prefix, compare the digest column only
        lines = (tmp_path / dirname / "SHA256SUMS").read_text().splitlines()
        return "\n".join(sorted(line.split("  ")[0] for line in lines))

    assert make("run_a") == make("run_b")


def test_manifest_deterministic_fields_are_stable(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    kwargs = {
        "run_id": "fixed",
        "created_at_utc": "2026-07-16T00:00:00Z",
        "repo_root": repo_root,
        "command_line": ["python", "-m", "scripts.base_train"],
        "resolved_config": {"mode": "counters"},
        "seed": 42,
    }
    m1 = build_manifest(**kwargs)
    m2 = build_manifest(**kwargs)
    # git/device/environment reflect live state but are identical within a run;
    # the caller-supplied deterministic fields must match exactly.
    for key in ("run_id", "created_at_utc", "command_line", "seed", "instrumentation_config"):
        assert m1[key] == m2[key]


def test_smoke_evidence_is_reproducible():
    """The nanochat smoke run's headline metrics are byte-frozen in
    VALIDATION-style docs; this guards the CWC-side deterministic reduction
    (FLOP ledger) that would feed such a bundle stays reproducible."""
    ledgers = [json.dumps(_build_ledger().to_dict(), sort_keys=True) for _ in range(5)]
    assert len(set(ledgers)) == 1  # all five runs identical
