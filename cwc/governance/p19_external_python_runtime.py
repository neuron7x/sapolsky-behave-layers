from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_PYTHON_RUNTIME_V1"
REQUIRED_IMPLEMENTATION = "cpython"
REQUIRED_MAJOR = 3
REQUIRED_MINOR = 10


class P19ExternalPythonRuntimeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalPythonRuntimeError(f"{name} must be lowercase SHA-256")
    return text


def _version_int(name: str, value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise P19ExternalPythonRuntimeError(f"{name} must be an integer") from exc
    if result < 0:
        raise P19ExternalPythonRuntimeError(f"{name} must be non-negative")
    return result


@dataclass(frozen=True, slots=True)
class P19ExternalPythonRuntimeIdentity:
    implementation: str
    version_major: int
    version_minor: int
    version_micro: int
    releaselevel: str
    serial: int
    cache_tag: str
    executable_path: str
    executable_sha256: str
    executable_bytes: int
    runtime_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {"schema": SCHEMA, **asdict(self)}


def _payload_from_mapping(doc: Mapping[str, object]) -> dict[str, object]:
    implementation = str(doc.get("implementation", "")).strip().lower()
    if implementation != REQUIRED_IMPLEMENTATION:
        raise P19ExternalPythonRuntimeError("external verifier regression requires CPython")
    major = _version_int("version_major", doc.get("version_major"))
    minor = _version_int("version_minor", doc.get("version_minor"))
    micro = _version_int("version_micro", doc.get("version_micro"))
    serial = _version_int("serial", doc.get("serial"))
    if (major, minor) != (REQUIRED_MAJOR, REQUIRED_MINOR):
        raise P19ExternalPythonRuntimeError(
            f"external verifier regression requires CPython {REQUIRED_MAJOR}.{REQUIRED_MINOR}.x"
        )
    releaselevel = str(doc.get("releaselevel", "")).strip()
    if releaselevel not in {"alpha", "beta", "candidate", "final"}:
        raise P19ExternalPythonRuntimeError("invalid Python releaselevel")
    cache_tag = str(doc.get("cache_tag", "")).strip()
    if not cache_tag or any(ch in cache_tag for ch in ("\x00", "\n", "\r")):
        raise P19ExternalPythonRuntimeError("Python cache_tag required")
    executable_path = str(doc.get("executable_path", "")).strip()
    if not executable_path or not Path(executable_path).is_absolute() or any(
        ch in executable_path for ch in ("\x00", "\n", "\r")
    ):
        raise P19ExternalPythonRuntimeError("Python executable_path must be an absolute path")
    executable_sha256 = _sha("executable_sha256", doc.get("executable_sha256"))
    executable_bytes = _version_int("executable_bytes", doc.get("executable_bytes"))
    if executable_bytes <= 0:
        raise P19ExternalPythonRuntimeError("Python executable_bytes must be positive")
    return {
        "implementation": implementation,
        "version_major": major,
        "version_minor": minor,
        "version_micro": micro,
        "releaselevel": releaselevel,
        "serial": serial,
        "cache_tag": cache_tag,
        "executable_path": executable_path,
        "executable_sha256": executable_sha256,
        "executable_bytes": executable_bytes,
    }


def verify_python_runtime_identity_document(doc: Mapping[str, object]) -> P19ExternalPythonRuntimeIdentity:
    if doc.get("schema") != SCHEMA:
        raise P19ExternalPythonRuntimeError("unexpected Python runtime identity schema")
    payload = _payload_from_mapping(doc)
    digest = _sha("runtime_digest", doc.get("runtime_digest"))
    if sha256_bytes(canonical_json_bytes(payload)) != digest:
        raise P19ExternalPythonRuntimeError("Python runtime identity digest mismatch")
    return P19ExternalPythonRuntimeIdentity(**payload, runtime_digest=digest)


def inspect_python_runtime(executable: Path) -> P19ExternalPythonRuntimeIdentity:
    source = Path(executable)
    if not source.is_absolute():
        raise P19ExternalPythonRuntimeError("Python executable must be resolved before inspection")
    resolved = source.resolve()
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise P19ExternalPythonRuntimeError("resolved Python executable missing/invalid")

    probe = (
        "import json,sys;"
        "print(json.dumps({"
        "'implementation':sys.implementation.name,"
        "'version_major':sys.version_info.major,"
        "'version_minor':sys.version_info.minor,"
        "'version_micro':sys.version_info.micro,"
        "'releaselevel':sys.version_info.releaselevel,"
        "'serial':sys.version_info.serial,"
        "'cache_tag':sys.implementation.cache_tag,"
        "'executable':sys.executable},sort_keys=True,separators=(',',':')))"
    )
    try:
        result = subprocess.run(
            [str(resolved), "-c", probe],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
    except OSError as exc:
        raise P19ExternalPythonRuntimeError("Python runtime probe could not execute") from exc
    if result.returncode != 0 or result.stderr:
        raise P19ExternalPythonRuntimeError("Python runtime probe failed")
    try:
        observed = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise P19ExternalPythonRuntimeError("Python runtime probe emitted invalid JSON") from exc
    if not isinstance(observed, dict):
        raise P19ExternalPythonRuntimeError("Python runtime probe payload malformed")
    observed_executable = Path(str(observed.pop("executable", ""))).resolve()
    if observed_executable != resolved:
        raise P19ExternalPythonRuntimeError("executed Python reports a different executable identity")

    payload = {
        **observed,
        "executable_path": str(resolved),
        "executable_sha256": sha256_file(resolved),
        "executable_bytes": resolved.stat().st_size,
    }
    normalized = _payload_from_mapping(payload)
    return P19ExternalPythonRuntimeIdentity(
        **normalized,
        runtime_digest=sha256_bytes(canonical_json_bytes(normalized)),
    )
