"""python -m pytest tests/test_instrumentation_manifest.py -v"""

from pathlib import Path

from cwc.instrumentation.manifest import build_manifest, device_manifest, environment_manifest, git_provenance

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_git_provenance_reads_real_repo_state():
    provenance = git_provenance(REPO_ROOT)
    assert provenance["git_commit"] is not None
    assert len(provenance["git_commit"]) == 40
    assert isinstance(provenance["git_dirty"], bool)


def test_device_manifest_reports_cuda_availability():
    manifest = device_manifest()
    assert isinstance(manifest["cuda_available"], bool)
    assert isinstance(manifest["total_vram_bytes"], int)


def test_environment_manifest_flags_mismatch_against_expected_torch():
    manifest = environment_manifest(expected_torch_version="99.99.99")
    assert manifest["environment_match"] is False
    assert manifest["expected_torch_version"] == "99.99.99"


def test_environment_manifest_hostname_is_hashed_not_raw():
    import socket

    manifest = environment_manifest()
    assert manifest["hostname_hash"] != socket.gethostname()
    assert len(manifest["hostname_hash"]) == 16


def test_build_manifest_assembles_all_required_sections():
    manifest = build_manifest(
        run_id="test-run-1",
        created_at_utc="2026-07-16T00:00:00Z",
        repo_root=REPO_ROOT,
        command_line=["python", "scripts/base_train.py"],
        resolved_config={"mode": "counters"},
        seed=42,
    )
    for key in (
        "run_id", "created_at_utc", "command_line", "git", "device",
        "environment", "instrumentation_config", "model_config", "seed",
        "compile_state", "attention_backend",
    ):
        assert key in manifest
    assert manifest["seed"] == 42


def test_manifest_never_contains_secret_like_keys():
    manifest = build_manifest(
        run_id="test-run-2",
        created_at_utc="2026-07-16T00:00:00Z",
        repo_root=REPO_ROOT,
        command_line=["python", "scripts/base_train.py"],
        resolved_config={},
    )
    # "token" is deliberately excluded: "tokenizer_identity" is a legitimate
    # field name that contains it as a substring.
    forbidden_substrings = ("api_key", "secret", "password", "access_token", "auth_token")
    serialized = str(manifest).lower()
    for forbidden in forbidden_substrings:
        assert forbidden not in serialized
