from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_external_python_runtime import (
    SCHEMA,
    P19ExternalPythonRuntimeError,
    verify_python_runtime_identity_document,
)


def _doc(**overrides) -> dict[str, object]:
    payload = {
        "implementation": "cpython",
        "version_major": 3,
        "version_minor": 10,
        "version_micro": 14,
        "releaselevel": "final",
        "serial": 0,
        "cache_tag": "cpython-310",
        "executable_path": "/opt/dgc/python3.10",
        "executable_sha256": "a" * 64,
        "executable_bytes": 123456,
    }
    payload.update(overrides)
    return {
        "schema": SCHEMA,
        **payload,
        "runtime_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def test_structural_cpython_310_runtime_identity_verifies():
    runtime = verify_python_runtime_identity_document(_doc())
    assert runtime.implementation == "cpython"
    assert (runtime.version_major, runtime.version_minor, runtime.version_micro) == (3, 10, 14)
    assert runtime.cache_tag == "cpython-310"


def test_python_311_is_rejected_even_with_self_consistent_runtime_digest():
    with pytest.raises(P19ExternalPythonRuntimeError, match="requires CPython 3.10.x"):
        verify_python_runtime_identity_document(_doc(version_minor=11, cache_tag="cpython-311"))


def test_pypy_is_rejected_even_with_self_consistent_runtime_digest():
    with pytest.raises(P19ExternalPythonRuntimeError, match="requires CPython"):
        verify_python_runtime_identity_document(_doc(implementation="pypy"))


def test_runtime_digest_substitution_is_rejected():
    doc = _doc()
    doc["runtime_digest"] = "b" * 64
    with pytest.raises(P19ExternalPythonRuntimeError, match="digest mismatch"):
        verify_python_runtime_identity_document(doc)


def test_executable_sha_must_be_canonical_sha256():
    doc = _doc(executable_sha256="xyz")
    with pytest.raises(P19ExternalPythonRuntimeError, match="lowercase SHA-256"):
        verify_python_runtime_identity_document(doc)


def test_executable_path_must_be_absolute():
    doc = _doc(executable_path="python3.10")
    with pytest.raises(P19ExternalPythonRuntimeError, match="absolute path"):
        verify_python_runtime_identity_document(doc)


def test_zero_byte_executable_is_rejected():
    doc = _doc(executable_bytes=0)
    with pytest.raises(P19ExternalPythonRuntimeError, match="positive"):
        verify_python_runtime_identity_document(doc)
