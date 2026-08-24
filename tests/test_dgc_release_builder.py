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


def test_all_green_legacy_booleans_cannot_authorize_product_release_without_pointer(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)

    def blocked(**kwargs):
        raise mod.ProductQualificationPointerError("pointer not activated")

    monkeypatch.setattr(mod, "verify_product_qualification_pointer", blocked)
    manifest = mod.build_release(root, tmp_path / "out", require_clean=False)
    assert manifest["evidence_status_mirror"]["mirror_product_qualified"] is True
    assert manifest["evidence_status_is_authority"] is False
    assert manifest["product_qualified"] is False
    assert manifest["release_authority"] == "RESEARCH_RELEASE_NOT_PRODUCT_QUALIFIED"
    assert manifest["production_control_authorized"] is False


def test_require_product_qualified_fails_when_pointer_replay_is_unavailable(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    monkeypatch.setattr(
        mod,
        "verify_product_qualification_pointer",
        lambda **kwargs: (_ for _ in ()).throw(mod.ProductQualificationPointerError("unconfigured")),
    )
    with pytest.raises(RuntimeError, match="terminal ledger/Global-V4 replay"):
        mod.build_release(
            root,
            tmp_path / "out",
            require_clean=False,
            require_product_qualified=True,
        )


def test_verified_pointer_is_the_only_product_release_authority(tmp_path, monkeypatch):
    root, files = _release_root(tmp_path)
    _patch_git_and_tracking(monkeypatch, root, files)
    qualification = SimpleNamespace(
        pointer_digest="1" * 64,
        generation_id="generation-1",
        ledger_path="artifacts/ledger.json",
        ledger_sha256="2" * 64,
        ledger_tip_receipt_digest="3" * 64,
        global_v4_authority_path="artifacts/global-v4.json",
        global_v4_authority_sha256="4" * 64,
        global_v4_authority_digest="5" * 64,
    )
    monkeypatch.setattr(mod, "verify_product_qualification_pointer", lambda **kwargs: qualification)
    manifest = mod.build_release(
        root,
        tmp_path / "out",
        require_clean=False,
        require_product_qualified=True,
    )
    assert manifest["product_qualified"] is True
    assert manifest["release_authority"] == "PRODUCT_QUALIFIED_LEDGER_GLOBAL_V4"
    assert manifest["qualification_authority"]["pointer_digest"] == "1" * 64
    assert manifest["qualification_authority"]["global_v4_authority_digest"] == "5" * 64
    assert manifest["production_control_authorized"] is False
