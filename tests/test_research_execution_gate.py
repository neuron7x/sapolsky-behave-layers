from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

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
