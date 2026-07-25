"""Static admission gate proving integrity contracts remain wired into inference."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_INVARIANTS = {
    "request": {"prompt_non_empty", "token_ids_in_vocabulary", "positive_sample_count",
                "finite_non_negative_temperature", "bounded_seed", "prompt_and_decode_fit_sequence"},
    "cache": {"positive_geometry", "synchronized_row_positions", "bounded_advance", "compatible_prefill"},
    "sampling": {"rank_two_non_empty_logits", "floating_logits", "finite_logits",
                 "seed_reproducibility", "greedy_seed_invariance"},
    "weights": {"complete_sorted_inventory", "shape_and_dtype_commitment", "finite_tensor_content",
                "per_tensor_sha256", "state_root_sha256", "single_bit_tamper_detection",
                "checkpoint_load_verification"},
}


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        contract = json.loads(
            (root / "engineering/inference_integrity_contract.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"inference integrity contract unreadable: {exc}"]
    if contract.get("schema_version") != 1:
        errors.append("inference integrity schema_version must be 1")
    actual = contract.get("invariants", {})
    for layer, required in REQUIRED_INVARIANTS.items():
        missing = required - set(actual.get(layer, []))
        if missing:
            errors.append(f"{layer} invariants missing: {sorted(missing)}")

    engine = (root / "nanochat/engine.py").read_text(encoding="utf-8")
    for token in (
        "validate_generation_request(",
        "validate_logits(logits)",
        'raise OverflowError("KV cache capacity exceeded")',
        'raise RuntimeError("KV cache rows have divergent positions")',
    ):
        if token not in engine:
            errors.append(f"real inference path is not wired to: {token}")

    integrity = (root / "nanochat/model_integrity.py").read_text(encoding="utf-8")
    for token in (
        "for name in sorted(state)",
        "torch.isfinite(value).all()",
        '"sha256": hashlib.sha256(payload).hexdigest()',
        '"state_sha256": hashlib.sha256(encoded).hexdigest()',
    ):
        if token not in integrity:
            errors.append(f"weight integrity implementation missing: {token}")
    checkpoint = (root / "nanochat/checkpoint_manager.py").read_text(encoding="utf-8")
    for token in (
        "build_state_manifest(model_data)",
        "verify_state_manifest(model_data, expected_integrity)",
        "Checkpoint weight integrity verification failed",
    ):
        if token not in checkpoint:
            errors.append(f"checkpoint path is not wired to: {token}")
    if "inference-integrity:" not in (root / "Makefile.cwc").read_text(encoding="utf-8"):
        errors.append("focused inference-integrity test target is not mandatory")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"INFERENCE-INTEGRITY: FAIL: {error}")
        return 1
    print("INFERENCE-INTEGRITY: PASS (request, cache, logits, weights, behaviour)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
