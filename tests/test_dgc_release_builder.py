import hashlib
import importlib.util
import json
import pathlib
import tarfile
from types import SimpleNamespace

import pytest

MODULE = pathlib.Path(__file__).parents[1] / "scripts/make_dgc_release.py"
spec = importlib.util.spec_from_file_location("make_dgc_release", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_deterministic_tar_is_byte_identical_and_normalizes_metadata(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "b.txt").write_text("b\n")
    (root / "a.txt").write_text("a\n")
    files = (root / "a.txt", root / "b.txt")
    one = tmp_path / "one.tar.gz"
    two = tmp_path / "two.tar.gz"
    assert mod.deterministic_tar_gz(root, files, one) == mod.deterministic_tar_gz(root, files, two)
    assert one.read_bytes() == two.read_bytes()
    with tarfile.open(one, "r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == ["a.txt", "b.txt"]
        assert all(member.mtime == 0 and member.uid == 0 and member.gid == 0 for member in members)


def _release_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    status_path = root / "artifacts/dgc-product-v1/evidence_status.json"
    status_path.parent.mkdir(parents=True)
    status = {field: True for field in mod.PRODUCT_FIELDS}
    status.update({"schema": "TEST", "status": "ALL_GREEN_MIRROR", "generated_on": "test"})
    status_path.write_text(json.dumps(status), encoding="utf-8")
    for rel in mod.CRITICAL_PATHS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("placeholder\n", encoding="utf-8")
    source = root / "source.py"
    source.write_text("x = 1\n", encoding="utf-8")
    extra_evidence = root / "artifacts/dgc-product-v1/raw.bin"
    extra_evidence.write_bytes(b"raw")
    files = tuple(sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    ))
    return root, files


def _patch_git_and_tracking(monkeypatch, root, files):
    def fake_git(_root, *args, text=True):
        if args == ("status", "--porcelain", "--untracked-files=no"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("rev-parse", "HEAD^{tree}"):
            return "b" * 40
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_git", fake_git)
    monkeypatch.setattr(mod, "tracked_paths", lambda _root: files)
    monkeypatch.setattr(mod, "tracked_paths_at_commit", lambda _root, _commit: ("source.py",))

    def fake_git_archive(_root, commit, destination):
        data = f"archive:{commit}".encode()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    monkeypatch.setattr(mod, "deterministic_git_archive_gz", fake_git_archive)


def _qualified_tuple(
    *,
    raw_transcripts: bool = True,
    plan_entrypoint: bool = True,
    dependency_closure: bool = True,
    dual_activation: bool = True,
    activation_regression: bool = True,
    portable_replay: bool = True,
    portable_v5: bool = True,
):
    qualification = SimpleNamespace(
        pointer_digest="1" * 64,
        generation_id="generation-1",
        repo_commit="c" * 40,
        repo_tree="d" * 40,
        ledger_path="artifacts/ledger.json",
        ledger_sha256="2" * 64,
        ledger_tip_receipt_digest="3" * 64,
        global_v5_authority_path="artifacts/global-v5.json",
        global_v5_authority_sha256="4" * 64,
        global_v5_authority_digest="5" * 64,
    )
    packaging = SimpleNamespace(document={
        "schema": "DGC_EVIDENCE_PACKAGING_AUTHORITY_V2",
        "qualified_execution_commit": "c" * 40,
        "qualified_execution_tree": "d" * 40,
        "packaging_commit": "a" * 40,
        "packaging_tree": "b" * 40,
        "global_v5_authority_digest": "5" * 64,
        "protected_execution_source_unchanged": True,
        "authority_digest": "6" * 64,
    })
    bundle_doc = {
        "schema": "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V7",
        "qualified_execution_commit": "c" * 40,
        "qualified_execution_tree": "d" * 40,
        "packaging_commit": "a" * 40,
        "packaging_tree": "b" * 40,
        "evidence_graph_complete": True,
        "all_required_subjects_git_bound": True,
        "raw_p19_verification_transcripts_included": raw_transcripts,
        "frozen_verification_plan_and_entrypoint_included": plan_entrypoint,
        "frozen_verifier_dependency_closure_included": dependency_closure,
        "dual_signed_verifier_activation_authority_included": dual_activation,
        "activation_regression_evidence_included": activation_regression,
        "portable_p19_replay_inputs_included": portable_replay,
        "portable_global_v5_authority_included": portable_v5,
        "global_v5_authority_digest": "5" * 64,
        "authority_digest": "7" * 64,
    }
    bundle = SimpleNamespace(
        document=bundle_doc,
        evidence_graph_complete=True,
        all_required_subjects_git_bound=True,
        raw_p19_verification_transcripts_included=raw_transcripts,
        frozen_verification_plan_and_entrypoint_included=plan_entrypoint,
        frozen_verifier_dependency_closure_included=dependency_closure,
        dual_signed_verifier_activation_authority_included=dual_activation,
        activation_regression_evidence_included=activation_regression,
        portable_p19_replay_inputs_included=portable_replay,
        portable_global_v5_authority_included=portable_v5,
    )
    return qualification, packaging, bundle


def test_all_green_legacy_booleans_cannot_authorize_product_release_without_graph_authority(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    monkeypatch.setattr(
        mod,
        "build_qualified_evidence_bundle_authority",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("pointer not activated")),
    )
    manifest = mod.build_release(root, tmp_path / "out", require_clean=False)
    assert manifest["evidence_status_mirror"]["mirror_product_qualified"] is True
    assert manifest["evidence_status_is_authority"] is False
    assert manifest["product_qualified"] is False
    assert manifest["release_authority"] == "RESEARCH_RELEASE_NOT_PRODUCT_QUALIFIED"
    assert manifest["production_control_authorized"] is False


def test_require_product_qualified_fails_when_portable_graph_replay_is_unavailable(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    monkeypatch.setattr(
        mod,
        "build_qualified_evidence_bundle_authority",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("unconfigured")),
    )
    with pytest.raises(RuntimeError, match="portable Global-V5 replay"):
        mod.build_release(root, tmp_path / "out", require_clean=False, require_product_qualified=True)


def test_product_release_requires_bundle_v7_dual_signed_activation_and_plan_v4(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    qualification, packaging, bundle = _qualified_tuple()
    monkeypatch.setattr(mod, "build_qualified_evidence_bundle_authority", lambda **kwargs: (qualification, packaging, bundle))
    manifest = mod.build_release(root, tmp_path / "out", require_clean=False, require_product_qualified=True)
    assert manifest["schema"] == "DGC_DETERMINISTIC_RESEARCH_RELEASE_V7"
    assert manifest["product_qualified"] is True
    assert manifest["release_authority"] == "PRODUCT_QUALIFIED_PORTABLE_GLOBAL_V5_T0_T1_GRAPH_COMPLETE_PLAN_V4_DUAL_SIGNED_ACTIVATION_V1"
    assert manifest["portable_global_v5_required_for_product_claim"] is True
    assert manifest["self_contained_raw_p19_verification_transcript_required_for_product_claim"] is True
    assert manifest["frozen_verification_plan_v4_and_entrypoint_required_for_product_claim"] is True
    assert manifest["frozen_verifier_dependency_closure_required_for_product_claim"] is True
    assert manifest["dual_signed_verifier_activation_authority_required_for_product_claim"] is True
    assert manifest["activation_regression_evidence_required_for_product_claim"] is True
    assert manifest["portable_p19_replay_inputs_required_for_product_claim"] is True
    assert manifest["environment_specific_signature_tool_receipt_is_product_authority"] is False
    assert manifest["qualification_authority"]["global_v5_authority_digest"] == "5" * 64
    assert manifest["qualified_evidence_bundle_authority"]["dual_signed_verifier_activation_authority_included"] is True
    assert manifest["production_control_authorized"] is False


@pytest.mark.parametrize(
    (
        "raw_transcripts",
        "plan_entrypoint",
        "dependency_closure",
        "dual_activation",
        "activation_regression",
        "portable_replay",
        "portable_v5",
    ),
    [
        (False, True, True, True, True, True, True),
        (True, False, True, True, True, True, True),
        (True, True, False, True, True, True, True),
        (True, True, True, False, True, True, True),
        (True, True, True, True, False, True, True),
        (True, True, True, True, True, False, True),
        (True, True, True, True, True, True, False),
    ],
)
def test_missing_any_bundle_v7_terminal_invariant_blocks_product_release(
    tmp_path,
    monkeypatch,
    raw_transcripts,
    plan_entrypoint,
    dependency_closure,
    dual_activation,
    activation_regression,
    portable_replay,
    portable_v5,
):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    qualification, packaging, bundle = _qualified_tuple(
        raw_transcripts=raw_transcripts,
        plan_entrypoint=plan_entrypoint,
        dependency_closure=dependency_closure,
        dual_activation=dual_activation,
        activation_regression=activation_regression,
        portable_replay=portable_replay,
        portable_v5=portable_v5,
    )
    monkeypatch.setattr(mod, "build_qualified_evidence_bundle_authority", lambda **kwargs: (qualification, packaging, bundle))
    with pytest.raises(RuntimeError, match="Bundle-V7"):
        mod.build_release(root, tmp_path / "out", require_clean=False, require_product_qualified=True)


def test_pointer_and_packaging_without_graph_complete_bundle_cannot_authorize_release(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    monkeypatch.setattr(
        mod,
        "build_qualified_evidence_bundle_authority",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("required raw subject not tracked in T_pkg")),
    )
    with pytest.raises(RuntimeError, match="required raw subject not tracked"):
        mod.build_release(root, tmp_path / "out", require_clean=False, require_product_qualified=True)
