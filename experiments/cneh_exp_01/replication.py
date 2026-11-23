"""Sealed cohort tooling: cryptographic consistency, never external authority.

The private reveal contains the seeds and a random 256-bit salt. Keep it with the
independent operator until outputs are published. Hashes cannot establish who
executed code, when publication happened, or whether blinding was maintained.
No timestamp, operator string, or self-attested Boolean upgrades that limitation.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import secrets
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DOMAIN = b"CNEH-EXP-01:SEALED-COHORT:v1\x00"
SCHEMA = "cneh-sealed-cohort-v1"
METADATA = {"schema", "experiment", "protocol_sha256", "code_sha", "operator_id",
            "cohort", "n_world_seeds"}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def loads_strict(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> Any:
        raise ValueError(f"nonfinite JSON value: {value}")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite JSON number")
        return number

    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject_constant,
                      parse_float=finite_float)


def read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("JSON input must be a regular non-symlink file")
    return loads_strict(path.read_text(encoding="utf-8"))


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in "0123456789abcdef" for c in value)


def _fields(value: Any, names: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("unexpected or missing document fields")


def _metadata(code_sha: str, operator_id: str) -> dict[str, Any]:
    if not _hex(code_sha, 40):
        raise ValueError("code_sha must identify an exact lowercase 40-hex Git commit")
    if (not isinstance(operator_id, str) or not 1 <= len(operator_id) <= 128
            or operator_id != operator_id.strip() or any(not c.isprintable() for c in operator_id)):
        raise ValueError("operator_id must be a nonempty printable identifier")
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = loads_strict(protocol_bytes.decode("utf-8"))
    return {"schema": SCHEMA, "experiment": "CNEH-EXP-01",
            "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
            "code_sha": code_sha, "operator_id": operator_id, "cohort": "REPLICATION",
            "n_world_seeds": protocol["cohorts"]["replication"]["n_world_seeds"]}


def _validate_metadata(document: dict[str, Any]) -> None:
    expected = _metadata(document["code_sha"], document["operator_id"])
    if (type(document["n_world_seeds"]) is not int
            or {key: document[key] for key in METADATA} != expected):
        raise ValueError("cohort identity or frozen protocol binding mismatch")


def _validate_public(document: Any) -> None:
    _fields(document, METADATA | {"commitment_sha256"})
    _validate_metadata(document)
    if not _hex(document["commitment_sha256"], 64):
        raise ValueError("invalid commitment digest")


def _validate_seeds(seeds: Any, count: int) -> None:
    if (not isinstance(seeds, list) or len(seeds) != count
            or any(type(seed) is not int or not 0 <= seed < 2**64 for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("invalid unique world-seed cohort")
    protocol = read_json(HERE / "protocol.json")
    primary = protocol["cohorts"]["primary"]
    excluded = set(range(primary["seed_first"], primary["seed_last"] + 1)) | {3001, 3002, 3003, 3004}
    excluded.update(read_json(HERE / "qualification_contract.json")["timing"]["seeds"])
    excluded.update(read_json(HERE / "bnsyn_integration_contract.json")["smoke"]["seeds"])
    if excluded.intersection(seeds):
        raise ValueError("replication seeds overlap an exposed PRIMARY or engineering cohort")


def create_commitment(seeds: list[int], *, code_sha: str, operator_id: str,
                      nonce: bytes | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return public commitment and PRIVATE reveal; no execution is authorized."""
    metadata = _metadata(code_sha, operator_id)
    _validate_seeds(seeds, metadata["n_world_seeds"])
    if nonce is None:
        nonce = secrets.token_bytes(32)
    if not isinstance(nonce, bytes) or len(nonce) != 32:
        raise ValueError("nonce must contain exactly 256 bits")
    reveal = {**metadata, "seeds": seeds.copy(), "nonce": nonce.hex()}
    commitment = {**metadata, "commitment_sha256": hashlib.sha256(DOMAIN + canonical(reveal)).hexdigest()}
    return commitment, reveal


def _output_hash(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("outputs must be a regular non-symlink file")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    if size == 0:
        raise ValueError("outputs must not be empty")
    return digest.hexdigest(), size


def seal_outputs(commitment: dict[str, Any], outputs: Path) -> dict[str, Any]:
    """Bind raw output bytes to a commitment; publication order remains unproven."""
    _validate_public(commitment)
    sha, size = _output_hash(outputs)
    return {"schema": "cneh-output-seal-v1", "commitment_sha256": commitment["commitment_sha256"],
            "outputs_sha256": sha, "outputs_bytes": size}


def verify_reveal(commitment: dict[str, Any], reveal: dict[str, Any], *,
                  output_seal: dict[str, Any] | None = None,
                  outputs: Path | None = None) -> dict[str, Any]:
    """Validate hash consistency. External identity/chronology are never inferred."""
    _validate_public(commitment)
    _fields(reveal, METADATA | {"seeds", "nonce"})
    _validate_metadata(reveal)
    if any(commitment[key] != reveal[key] for key in METADATA):
        raise ValueError("commitment/reveal metadata mismatch")
    _validate_seeds(reveal["seeds"], reveal["n_world_seeds"])
    if not _hex(reveal["nonce"], 64):
        raise ValueError("invalid 256-bit nonce")
    observed = hashlib.sha256(DOMAIN + canonical(reveal)).hexdigest()
    if not hmac.compare_digest(observed, commitment["commitment_sha256"]):
        raise ValueError("commitment/reveal digest mismatch")
    if (output_seal is None) != (outputs is None):
        raise ValueError("output seal and raw outputs must be supplied together")
    seal_status = "NOT_TESTED"
    if output_seal is not None:
        _fields(output_seal, {"schema", "commitment_sha256", "outputs_sha256", "outputs_bytes"})
        if type(output_seal["outputs_bytes"]) is not int or output_seal != seal_outputs(commitment, outputs):
            raise ValueError("output seal does not bind these raw output bytes and commitment")
        seal_status = "PASS"
    return {"schema": "cneh-commitment-verification-v1", "consistency": "PASS",
            "output_seal": seal_status, "authority": "EXTERNAL_ATTESTATION_REQUIRED",
            "chronology": "NOT_AUTHENTICATED", "independent_blind_replication": False,
            "scientific_promotion_authorized": False,
            "commitment_sha256": commitment["commitment_sha256"],
            "required_external_order": ["commitment_published", "outputs_published", "reveal_published"],
            "required_external_checks": ["authenticated_separate_operator", "code_and_environment_identity",
                                         "seed_and_arm_label_blinding", "chronology_attestation",
                                         "all_preregistered_outputs_accounted_for"]}


def _write_new(path: Path, value: Any, *, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="create public commitment and private reveal")
    prepare.add_argument("--seeds", type=Path, required=True)
    prepare.add_argument("--code-sha", required=True)
    prepare.add_argument("--operator-id", required=True)
    prepare.add_argument("--out", type=Path, required=True)
    seal = sub.add_parser("seal", help="hash raw outputs; does not attest publication time")
    seal.add_argument("--commitment", type=Path, required=True)
    seal.add_argument("--outputs", type=Path, required=True)
    seal.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="check consistency; cannot authenticate independence")
    verify.add_argument("--commitment", type=Path, required=True)
    verify.add_argument("--reveal", type=Path, required=True)
    verify.add_argument("--output-seal", type=Path)
    verify.add_argument("--outputs", type=Path)
    verify.add_argument("--require-independent", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            public, private = create_commitment(read_json(args.seeds), code_sha=args.code_sha,
                                                operator_id=args.operator_id)
            args.out.mkdir(parents=False, exist_ok=False)
            (args.out / "private").mkdir(mode=0o700)
            _write_new(args.out / "private" / "reveal.json", private, mode=0o600)
            _write_new(args.out / "commitment.json", public)
            result = {"status": "COMMITMENT_PREPARED", "authority": "EXTERNAL_ATTESTATION_REQUIRED"}
        elif args.command == "seal":
            result = seal_outputs(read_json(args.commitment), args.outputs)
            _write_new(args.out, result)
        else:
            result = verify_reveal(read_json(args.commitment), read_json(args.reveal),
                                   output_seal=read_json(args.output_seal) if args.output_seal else None,
                                   outputs=args.outputs)
        print(canonical(result).decode("utf-8"), end="")
        return 2 if args.command == "verify" and args.require_independent else 0
    except (ValueError, OSError) as error:
        print(canonical({"status": "INVALID", "error": str(error)}).decode("utf-8"), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
