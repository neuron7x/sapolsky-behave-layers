import importlib.util
import pathlib
import tarfile

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


def test_product_and_production_authority_are_separate():
    status = {field: True for field in mod.PRODUCT_FIELDS}
    assert mod._product_qualified(status)
    assert mod._production_control_authorized(status)
    status["production_provider_trace_supported"] = False
    assert mod._product_qualified(status)
    assert not mod._production_control_authorized(status)
    status["external_real_workload_supported"] = False
    assert not mod._product_qualified(status)
