from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "scripts/research_execution_gate.py"
spec = importlib.util.spec_from_file_location("research_execution_gate", MODPATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _copy_fixture(tmp_path: Path) -> Path:
    for rel in (
        "artifacts/research-s01-skill-luck",
        "artifacts/research-s01-ood-credit",
        "artifacts/research-s03-latent-dynamics",
    ):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / rel, dst)
    (tmp_path / "research").mkdir(exist_ok=True)
    for name in ("09_KILLED_HYPOTHESES.yaml", "08_REPRODUCTION_QUEUE.yaml"):
        shutil.copy2(ROOT / "research" / name, tmp_path / "research" / name)
    return tmp_path


def test_current_execution_bundle_passes() -> None:
    mod.validate(ROOT)


def test_tampered_positive_artifact_fails_checksum(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    p = root / "artifacts/research-s01-ood-credit/verdict.json"
    data = json.loads(p.read_text())
    data["architecture_promotion_authority"] = True
    p.write_text(json.dumps(data))
    try:
        mod.validate(root)
    except ValueError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("tampered evidence was accepted")


def test_erased_negative_result_fails_even_with_resealed_checksum(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    d = root / "artifacts/research-s03-latent-dynamics"
    p = d / "verdict.json"
    data = json.loads(p.read_text())
    data["verdict"] = "S03_CONTROLLED_LATENT_DYNAMICS_QUALIFIED"
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    # Simulate an attacker who also rewrites the checksum ledger.
    import hashlib
    lines=[]
    for line in (d / "SHA256SUMS").read_text().splitlines():
        digest,name=line.split("  ",1)
        if name=="verdict.json": digest=hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (d / "SHA256SUMS").write_text("\n".join(lines)+"\n")
    try:
        mod.validate(root)
    except ValueError as exc:
        assert "negative verdict" in str(exc)
    else:
        raise AssertionError("erased negative verdict was accepted")


def _reseal(directory: Path, name: str) -> None:
    ledger = directory / "SHA256SUMS"
    replacement = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    pairs = [line.split("  ", 1) for line in ledger.read_text().splitlines()]
    ledger.write_text("".join(f"{replacement if key == name else digest}  {key}\n"
                              for digest, key in pairs))


@pytest.mark.parametrize("fault", ["empty", "omit-verdict", "duplicate"])
def test_ledger_cannot_drop_or_duplicate_required_entries(tmp_path: Path, fault: str) -> None:
    root = _copy_fixture(tmp_path)
    ledger = root / "artifacts/research-s01-ood-credit/SHA256SUMS"
    rows = ledger.read_text().splitlines()
    replacement = {"empty": [], "omit-verdict": rows[1:], "duplicate": rows + rows[:1]}[fault]
    ledger.write_text("\n".join(replacement) + "\n")
    with pytest.raises(ValueError, match="checksum"):
        mod.validate(root)


@pytest.mark.parametrize("fault", ["missing", "empty", "partial", "not-boolean"])
def test_checksum_does_not_replace_exact_predicates(tmp_path: Path, fault: str) -> None:
    root = _copy_fixture(tmp_path)
    path = root / "artifacts/research-s01-ood-credit/verdict.json"
    document = json.loads(path.read_text())
    if fault == "missing":
        del document["primary_predicates"]
    elif fault == "empty":
        document["primary_predicates"] = {}
    elif fault == "partial":
        del document["primary_predicates"]["ood_shapley_unique_A_all"]
    else:
        document["primary_predicates"]["ood_shapley_unique_A_all"] = 1
    path.write_text(json.dumps(document))
    _reseal(path.parent, path.name)
    with pytest.raises(ValueError, match="primary predicate"):
        mod.validate(root)


@pytest.mark.parametrize("fault, expected", [
    ("contradiction", "primary predicate contradicted at 1000/OOD_SIGN_FLIP/EXACT_CF_SHAPLEY"),
    ("missing", "seed roster incomplete at 1000/OOD_SIGN_FLIP/EXACT_CF_SHAPLEY"),
    ("duplicate", "duplicate seed row at 1000/OOD_SIGN_FLIP/EXACT_CF_SHAPLEY"),
    ("efficiency", "efficiency predicate contradicted at 1000/OOD_SIGN_FLIP/EXACT_CF_SHAPLEY"),
])
def test_resealed_rows_cannot_support_stale_outcomes(tmp_path: Path, fault: str, expected: str) -> None:
    root = _copy_fixture(tmp_path)
    directory = root / "artifacts/research-s01-ood-credit"
    path = directory / "seed_results.csv"
    verdict = (directory / "verdict.json").read_bytes()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    index = next(i for i, row in enumerate(rows)
                 if (row["seed"], row["context"], row["method"]) ==
                 ("1000", "OOD_SIGN_FLIP", "EXACT_CF_SHAPLEY"))
    if fault == "contradiction":
        rows[index].update(top1_A="0", false_credit_mass="1.0", score_A="0.0", score_C="0.0",
                           score_D="1.0", score_B="0.0")
    elif fault == "missing":
        rows.pop(index)
    elif fault == "duplicate":
        rows.insert(index, rows[index])
    else:
        rows[index]["max_efficiency_error"] = "1e-10"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    _reseal(directory, path.name)
    assert (directory / "verdict.json").read_bytes() == verdict
    with pytest.raises(ValueError, match=expected):
        mod.validate(root)
