"""Canonical, content-addressed integrity manifests for model weights."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import torch
from torch import Tensor


def _tensor_bytes(tensor: Tensor) -> bytes:
    if tensor.layout != torch.strided:
        raise TypeError("only strided tensors can be integrity-manifested")
    if tensor.device.type == "meta":
        raise ValueError("meta tensors have no weight content")
    value = tensor.detach().contiguous().cpu()
    if (value.is_floating_point() or value.is_complex()) and not torch.isfinite(value).all():
        raise FloatingPointError("model state contains NaN or infinity")
    return bytes(value.view(torch.uint8).numpy().tobytes())


def build_state_manifest(state: Mapping[str, Tensor]) -> dict[str, Any]:
    """Return a deterministic inventory and SHA-256 Merkle-style root for a state dict."""
    entries: list[dict[str, Any]] = []
    for name in sorted(state):
        tensor = state[name]
        if not isinstance(name, str) or not name:
            raise ValueError("state keys must be non-empty strings")
        if not isinstance(tensor, Tensor):
            raise TypeError(f"state entry {name!r} is not a tensor")
        payload = _tensor_bytes(tensor)
        entries.append(
            {
                "name": name,
                "shape": list(tensor.shape),
                "dtype": str(tensor.dtype),
                "numel": tensor.numel(),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    encoded = json.dumps(entries, separators=(",", ":"), sort_keys=True).encode()
    return {
        "schema_version": 1,
        "algorithm": "sha256",
        "tensor_count": len(entries),
        "parameter_count": sum(int(item["numel"]) for item in entries),
        "state_sha256": hashlib.sha256(encoded).hexdigest(),
        "tensors": entries,
    }


def verify_state_manifest(state: Mapping[str, Tensor], expected: Mapping[str, Any]) -> list[str]:
    """Explain every top-level integrity mismatch; an empty result is verified."""
    try:
        actual = build_state_manifest(state)
    except (TypeError, ValueError, FloatingPointError) as exc:
        return [str(exc)]
    errors = []
    for field in ("schema_version", "algorithm", "tensor_count", "parameter_count", "state_sha256"):
        if actual.get(field) != expected.get(field):
            errors.append(f"{field}: expected {expected.get(field)!r}, got {actual.get(field)!r}")
    if actual["tensors"] != expected.get("tensors"):
        errors.append("tensor inventory, shape, dtype, or content digest differs")
    return errors
