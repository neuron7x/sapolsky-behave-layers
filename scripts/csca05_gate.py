#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/csca-05-runtime"
VERDICT = ROOT / "research/results/CSCA-05-RUNTIME/verdict.json"


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    errors = []
    required = [
        ART / "calibration/calibration_result.json",
        ART / "calibration/frozen_policy.json",
        ART / "primary/result.json",
        ART / "replication/result.json",
        ART / "diagnostics/intervention_semantics/summary.json",
        ART / "diagnostics/recency_baseline.json",
        VERDICT,
    ]
    for p in required:
        if not p.is_file():
            errors.append(f"missing {p.relative_to(ROOT)}")
    if errors:
        print("CSCA05-GATE FAIL")
        for e in errors: print(" -", e)
        return 1

    cal = json.loads((ART / "calibration/calibration_result.json").read_text())
    policy = json.loads((ART / "calibration/frozen_policy.json").read_text())
    primary = json.loads((ART / "primary/result.json").read_text())
    repl = json.loads((ART / "replication/result.json").read_text())
    verdict = json.loads(VERDICT.read_text())
    if not cal.get("calibration_pass") or cal.get("chosen_budget") != policy.get("chosen_antithetic_pairs"):
        errors.append("calibration/policy mismatch")
    if cal.get("delta") != policy.get("delta"):
        errors.append("frozen delta mismatch")
    for name, result in (("PRIMARY", primary), ("REPLICATION", repl)):
        if not result.get("cohort_pass"):
            errors.append(f"{name} cohort_pass false")
        for stratum in ("pooled", "PROSE", "CODE"):
            m = result["metrics"][stratum]
            if m["false_authority_count"] != 0:
                errors.append(f"{name}/{stratum} false authority")
            if m["top_accuracy_given_accept"] != 1.0:
                errors.append(f"{name}/{stratum} accepted accuracy != 1")
            if m["coverage"] < policy["min_coverage"]:
                errors.append(f"{name}/{stratum} coverage below frozen minimum")
        if result["noninterference"]["output_mismatch_count"] != 0:
            errors.append(f"{name} shadow changed base output")
        if result["noninterference"]["model_state_mutation_count"] != 0:
            errors.append(f"{name} shadow mutated model state")
        if result.get("active_control") is not False:
            errors.append(f"{name} active control illegally enabled")
        trace_dir = ART / name.lower() / "traces"
        # Preserve the authoritative generation order used by run.py:
        # PROSE[0..31] followed by CODE[0..31].  Lexicographic filename
        # order would place CODE before PROSE and falsely invalidate the
        # sealed manifest despite every individual trace hash matching.
        def _trace_order(path: Path) -> tuple[int, int, str]:
            match = re.search(r"-(PROSE|CODE)-(\d+)\.json$", path.name)
            if match is None:
                return (9, 0, path.name)
            return (0 if match.group(1) == "PROSE" else 1, int(match.group(2)), path.name)
        traces = sorted(trace_dir.glob("*.json"), key=_trace_order)
        if len(traces) != result["trace_count"]:
            errors.append(f"{name} trace count mismatch")
        manifest = []
        for path in traces:
            payload = json.loads(path.read_text())
            expected = payload.pop("trace_sha256", None)
            got = _canonical_hash(payload)
            if expected != got:
                errors.append(f"{name} trace hash mismatch {path.name}")
            if payload.get("active_control") is not False:
                errors.append(f"{name} trace active control {path.name}")
            if payload.get("model_state_hash_before") != payload.get("model_state_hash_after"):
                errors.append(f"{name} trace model mutation {path.name}")
            if payload.get("authority_scope") != "CONTEXT_ONLY":
                errors.append(f"{name} trace unscoped authority {path.name}")
            manifest.append(expected)
        if _canonical_hash(manifest) != result["trace_manifest_sha256"]:
            errors.append(f"{name} trace manifest hash mismatch")

    if verdict.get("verdict") != "DIRECT_INTERVENTION_SHADOW_RUNTIME_QUALIFIED_NARROWED":
        errors.append("unexpected verdict")
    if verdict.get("scientific_pass") is not True:
        errors.append("scientific_pass false")
    if verdict.get("shadow_runtime_path_qualified_narrowed") is not True:
        errors.append("narrow shadow path not qualified")
    for key in (
        "general_shadow_inference_qualified",
        "real_model_replay_qualified",
        "physical_gpu_compute_qualified",
        "active_causal_control_authorized",
        "h5_architecture_integration_authorized",
    ):
        if verdict.get(key) is not False:
            errors.append(f"illegal promotion: {key}")
    rd03 = json.loads((ROOT / "research/results/ACT-RD-03/verdict.json").read_text())
    # ACT-R&D-03 predates the `scientific_pass` field. Preserve its actual
    # negative authority contract rather than requiring a nonexistent key.
    if rd03.get("scientific_eval") != "FAIL":
        errors.append("ACT-R&D-03 scientific_eval no longer FAIL")
    if rd03.get("scientific_verdict") != "UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE":
        errors.append("ACT-R&D-03 negative scientific verdict was overwritten")
    if rd03.get("current_authority") != "RESEARCH_ONLY":
        errors.append("ACT-R&D-03 authority was silently promoted")
    rd03_authority = rd03.get("authority", {})
    if any(rd03_authority.get(key) is not False for key in (
        "active_causal_control_authorized",
        "architecture_promotion_authority",
        "physical_compute_authorized",
        "real_model_replay_authorized",
        "shadow_inference_authorized",
    )):
        errors.append("ACT-R&D-03 negative authority boundary was overwritten")

    if errors:
        print(f"CSCA05-GATE FAIL ({len(errors)})")
        for e in errors: print(" -", e)
        return 1
    print("CSCA05-GATE PASS: direct-intervention shadow path replicated; no broad/active promotion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
