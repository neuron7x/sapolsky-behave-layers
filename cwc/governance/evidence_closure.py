from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

SCHEMA = "DGC_EVIDENCE_CLOSURE_LEDGER_V2"
RECEIPT_SCHEMA = "DGC_EVIDENCE_CLOSURE_RECEIPT_V2"
_GENERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# A final evaluation harness includes the executable-frozen B0-B3 panel. Therefore
# B2 must be fitted before HARNESS_FROZEN. CCF oracle semantics and the complete
# G1-G5 generalization registry are frozen before any B2 outcomes so neither
# headroom nor generalization definitions can be selected post-hoc.
STAGES: tuple[str, ...] = (
    "SOURCE_VERIFIED",
    "MATERIALIZED_VERIFIED",
    "EXECUTION_MANIFESTS_FROZEN",
    "CCF_SPEC_FROZEN",
    "GENERALIZATION_REGISTRY_FROZEN",
    "B2_FITTED",
    "HARNESS_FROZEN",
    "TRIAL_SIZED",
    "GENERATION_ROOT_FROZEN",
    "CONFIRMATORY_EXECUTED",
    "P9_SUPPORTED",
    "GENERALIZATION_SUPPORTED",
    "INDEPENDENT_REPLICATION_SUPPORTED",
    "P19_SEALED",
    "PRODUCT_QUALIFIED",
)


class ClosureError(RuntimeError):
    """Raised when an evidence-closure transition is not admissible."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_hex_digest(name: str, value: str) -> str:
    value = str(value).lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ClosureError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    path: str
    sha256: str
    minimum_bytes: int = 1

    def __post_init__(self) -> None:
        if not self.path or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ClosureError("evidence path must be a non-empty repository-relative path")
        object.__setattr__(self, "sha256", _validate_hex_digest("artifact.sha256", self.sha256))
        if self.minimum_bytes < 1:
            raise ClosureError("minimum_bytes must be >= 1")


@dataclass(frozen=True, slots=True)
class StageExecution:
    stage: str
    commands: tuple[tuple[str, ...], ...]
    evidence: tuple[EvidenceArtifact, ...]

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ClosureError(f"unknown stage: {self.stage}")
        if not self.evidence:
            raise ClosureError("stage execution must bind at least one evidence artifact")
        for command in self.commands:
            if not command or any(not part for part in command):
                raise ClosureError("commands must be non-empty argv vectors")


Runner = Callable[[Sequence[str], Path, Mapping[str, str]], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class EvidenceClosureLedger:
    """Fail-closed, digest-bound promotion ledger for external DGC evidence.

    This object does not decide whether an experiment is scientifically valid. It only
    prevents stage skipping, unbound evidence substitution, source-identity drift and
    silent command failure while executing an already frozen validation protocol.
    """

    def __init__(
        self,
        *,
        repository_root: Path,
        ledger_path: Path,
        generation_id: str,
        repo_commit: str,
        repo_tree: str,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.ledger_path = ledger_path.resolve()
        self.generation_id = generation_id
        self.repo_commit = repo_commit.lower()
        self.repo_tree = repo_tree.lower()
        if _GENERATION_ID_RE.fullmatch(generation_id) is None:
            raise ClosureError("generation_id must be a safe 1-128 character slug")
        for name, value in (("repo_commit", self.repo_commit), ("repo_tree", self.repo_tree)):
            if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
                raise ClosureError(f"{name} must be a 40-character lowercase Git object id")
        if not self.repository_root.is_dir():
            raise ClosureError("repository_root must exist")
        try:
            self.ledger_path.relative_to(self.repository_root)
        except ValueError as exc:
            raise ClosureError("ledger_path must remain inside repository root") from exc

    def _empty_state(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "generation_id": self.generation_id,
            "repo_commit": self.repo_commit,
            "repo_tree": self.repo_tree,
            "completed_stages": [],
            "receipts": [],
            "product_qualified": False,
        }

    def load(self) -> dict[str, object]:
        if not self.ledger_path.exists():
            return self._empty_state()
        data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        expected_identity = {
            "schema": SCHEMA,
            "generation_id": self.generation_id,
            "repo_commit": self.repo_commit,
            "repo_tree": self.repo_tree,
        }
        for key, expected in expected_identity.items():
            if data.get(key) != expected:
                raise ClosureError(f"ledger identity mismatch for {key}")
        completed = data.get("completed_stages")
        receipts = data.get("receipts")
        if not isinstance(completed, list) or not isinstance(receipts, list):
            raise ClosureError("ledger stage/receipt arrays are malformed")
        if completed != list(STAGES[: len(completed)]):
            raise ClosureError("ledger contains a stage skip or out-of-order transition")
        if len(receipts) != len(completed):
            raise ClosureError("receipt count does not match completed stages")
        previous: str | None = None
        for index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict) or receipt.get("stage") != completed[index]:
                raise ClosureError("receipt stage order is malformed")
            payload = dict(receipt)
            observed_digest = payload.pop("receipt_digest", None)
            if observed_digest != _sha256_bytes(_canonical_json(payload)):
                raise ClosureError("receipt digest mismatch")
            if payload.get("prior_receipt_digest") != previous:
                raise ClosureError("receipt chain mismatch")
            previous = observed_digest
        derived = completed == list(STAGES)
        if data.get("product_qualified") is not derived:
            raise ClosureError("product_qualified is not derivable from the completed stage chain")
        return data

    def next_stage(self) -> str | None:
        state = self.load()
        completed = state["completed_stages"]
        assert isinstance(completed, list)
        return None if len(completed) == len(STAGES) else STAGES[len(completed)]

    def _verify_artifacts(self, artifacts: Sequence[EvidenceArtifact]) -> list[dict[str, object]]:
        observed: list[dict[str, object]] = []
        seen: set[str] = set()
        for artifact in artifacts:
            if artifact.path in seen:
                raise ClosureError(f"duplicate evidence path: {artifact.path}")
            seen.add(artifact.path)
            path = (self.repository_root / artifact.path).resolve()
            try:
                path.relative_to(self.repository_root)
            except ValueError as exc:
                raise ClosureError("evidence path escapes repository root") from exc
            if not path.is_file() or path.is_symlink():
                raise ClosureError(f"missing regular evidence artifact: {artifact.path}")
            size = path.stat().st_size
            if size < artifact.minimum_bytes:
                raise ClosureError(f"evidence artifact too small: {artifact.path}")
            digest = sha256_file(path)
            if digest != artifact.sha256:
                raise ClosureError(f"evidence SHA-256 mismatch: {artifact.path}")
            observed.append({"path": artifact.path, "sha256": digest, "bytes": size})
        return observed

    def advance(
        self,
        execution: StageExecution,
        *,
        runner: Runner = _default_runner,
        extra_env: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        expected_stage = self.next_stage()
        if expected_stage is None:
            raise ClosureError("ledger is already PRODUCT_QUALIFIED")
        if execution.stage != expected_stage:
            raise ClosureError(f"stage skip rejected: expected {expected_stage}, got {execution.stage}")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repository_root)
        if extra_env:
            env.update(extra_env)
        command_records: list[dict[str, object]] = []
        for argv in execution.commands:
            result = runner(argv, self.repository_root, env)
            record = {
                "argv": list(argv),
                "returncode": int(result.returncode),
                "stdout_sha256": _sha256_bytes((result.stdout or "").encode("utf-8")),
                "stderr_sha256": _sha256_bytes((result.stderr or "").encode("utf-8")),
            }
            command_records.append(record)
            if result.returncode != 0:
                raise ClosureError(f"stage command failed ({result.returncode}): {' '.join(argv)}")

        evidence = self._verify_artifacts(execution.evidence)
        state = self.load()
        receipts = list(state["receipts"])
        prior_digest = receipts[-1]["receipt_digest"] if receipts else None
        receipt_payload: dict[str, object] = {
            "schema": RECEIPT_SCHEMA,
            "generation_id": self.generation_id,
            "repo_commit": self.repo_commit,
            "repo_tree": self.repo_tree,
            "stage": execution.stage,
            "prior_receipt_digest": prior_digest,
            "commands": command_records,
            "evidence": evidence,
        }
        receipt = dict(receipt_payload)
        receipt["receipt_digest"] = _sha256_bytes(_canonical_json(receipt_payload))
        receipts.append(receipt)
        completed = list(state["completed_stages"])
        completed.append(execution.stage)
        new_state = {
            "schema": SCHEMA,
            "generation_id": self.generation_id,
            "repo_commit": self.repo_commit,
            "repo_tree": self.repo_tree,
            "completed_stages": completed,
            "receipts": receipts,
            "product_qualified": completed == list(STAGES),
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        tmp.write_bytes(_canonical_json(new_state) + b"\n")
        os.replace(tmp, self.ledger_path)
        return receipt
