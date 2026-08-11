import json
from pathlib import Path

from scripts.verify_npi_01_result import verify


def _copy_json(src: Path, dst: Path) -> None:
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_independent_verifier_accepts_sealed_result(tmp_path: Path) -> None:
    raw = Path("artifacts/npi-01/raw_result.json")
    verdict = Path("artifacts/npi-01/verdict.json")
    assert verify(raw, verdict) == []


def test_independent_verifier_kills_radius_mutation(tmp_path: Path) -> None:
    raw_src = Path("artifacts/npi-01/raw_result.json")
    verdict_src = Path("artifacts/npi-01/verdict.json")
    raw = tmp_path / "raw.json"
    verdict = tmp_path / "verdict.json"
    _copy_json(raw_src, raw)
    _copy_json(verdict_src, verdict)
    data = json.loads(raw.read_text())
    data["radii"][0]["distance"] = data["radii"][0]["radius"]
    raw.write_text(json.dumps(data))
    assert verify(raw, verdict)


def test_independent_verifier_kills_curvature_mutation(tmp_path: Path) -> None:
    raw_src = Path("artifacts/npi-01/raw_result.json")
    verdict_src = Path("artifacts/npi-01/verdict.json")
    raw = tmp_path / "raw.json"
    verdict = tmp_path / "verdict.json"
    _copy_json(raw_src, raw)
    _copy_json(verdict_src, verdict)
    data = json.loads(raw.read_text())
    data["radii"][1]["k"] = "1/1"
    raw.write_text(json.dumps(data))
    assert verify(raw, verdict)


def test_independent_verifier_kills_verdict_mutation(tmp_path: Path) -> None:
    raw_src = Path("artifacts/npi-01/raw_result.json")
    verdict_src = Path("artifacts/npi-01/verdict.json")
    raw = tmp_path / "raw.json"
    verdict = tmp_path / "verdict.json"
    _copy_json(raw_src, raw)
    _copy_json(verdict_src, verdict)
    data = json.loads(verdict.read_text())
    data["verdict"] = "SUPPORTED"
    verdict.write_text(json.dumps(data))
    assert verify(raw, verdict)
