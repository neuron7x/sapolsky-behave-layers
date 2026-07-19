import json

from scripts.validate_evidence import validate


def test_rejects_seed_filename_mismatch(tmp_path):
    raw = tmp_path / "artifacts" / "wp-test" / "raw_runs"
    raw.mkdir(parents=True)
    (tmp_path / "artifacts" / "wp-test" / "RESULTS.md").write_text("result")
    (tmp_path / "artifacts" / "wp-test" / "SHA256SUMS").write_text("hash")
    (raw / "seed3.json").write_text(json.dumps({"seed": 4, "metric": 0.5}))
    assert any("payload seed 4 != filename seed 3" in error for error in validate(tmp_path))


def test_rejects_nonfinite_numbers(tmp_path):
    path = tmp_path / "payload.json"
    path.write_text('{"metric": NaN}')
    assert any("non-finite" in error for error in validate(tmp_path))


def test_rejects_probability_outside_unit_interval(tmp_path):
    path = tmp_path / "payload.json"
    path.write_text('{"route_auroc": 1.2}')
    assert any("outside [0,1]" in error for error in validate(tmp_path))
