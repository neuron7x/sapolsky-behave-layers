from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
from dataclasses import asdict
from pathlib import Path

from cwc.governance.external_materialization import (
    parse_terminal_dataset_manifest,
    verify_swe_parquet,
    verify_terminal_git_checkout,
)
from cwc.governance.external_source_authority import (
    ExternalSourceAuthority,
    ExternalSourceStage,
    promote_materialized_verified,
)
from cwc.governance.workload_seal import seal_materialized_workload

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"


def _run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "DGC-external-materializer/1"})
    with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    temp.replace(destination)


def _source_authority(row: dict) -> ExternalSourceAuthority:
    verification = row["verification"]
    authority = ExternalSourceAuthority(
        family_id=row["family_id"],
        stage=ExternalSourceStage.SOURCE_VERIFIED,
        upstream_revision=row["upstream_revision"],
        upstream_identity_digest=row["upstream_identity_digest"],
        source_verification_method=verification["verification_method"],
        source_verification_evidence_digest=row["source_verification_evidence_digest"],
    )
    if authority.digest != row["authority_digest"]:
        raise ValueError(f"source authority digest mismatch for {row['family_id']}")
    return authority


def _materialize_swe(row: dict, output_root: Path) -> dict:
    identity = row["identity"]
    family_root = output_root / "SWE_BENCH_VERIFIED"
    parquet = family_root / "data" / "test-00000-of-00001.parquet"
    url = (
        "https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/resolve/"
        f"{identity['revision']}/{identity['parquet_path']}?download=true"
    )
    _download(url, parquet)
    verified = verify_swe_parquet(
        parquet,
        expected_sha256=identity["parquet_sha256"],
        expected_bytes=None,
        expected_count=int(identity["expected_task_count"]),
    )
    seal = seal_materialized_workload(
        family_id=row["family_id"],
        root=family_root,
        task_ids=verified.instance_ids,
        expected_task_count=int(identity["expected_task_count"]),
    )
    authority = promote_materialized_verified(
        _source_authority(row),
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
    )
    return {
        "family_id": row["family_id"],
        "stage": authority.stage.name,
        "authority_digest": authority.digest,
        "source_authority_digest": row["authority_digest"],
        "parquet": {
            "bytes_size": verified.bytes_size,
            "sha256": verified.sha256,
            "row_count": verified.row_count,
            "instance_id_manifest_sha256": verified.task_manifest_sha256,
        },
        "workload_seal": asdict(seal),
    }


def _materialize_terminal(row: dict, output_root: Path) -> dict:
    identity = row["identity"]
    checkout = output_root / "TERMINAL_BENCH_2_1" / "repo"
    checkout.mkdir(parents=True, exist_ok=False)
    _run("git", "init", "-q", str(checkout))
    _run(
        "git",
        "-C",
        str(checkout),
        "remote",
        "add",
        "origin",
        f"https://github.com/{identity['repository']}.git",
    )
    _run(
        "git",
        "-C",
        str(checkout),
        "fetch",
        "--depth",
        "1",
        "origin",
        identity["commit"],
    )
    _run("git", "-C", str(checkout), "checkout", "-q", "--detach", "FETCH_HEAD")
    git_identity = verify_terminal_git_checkout(
        checkout,
        expected_commit=identity["commit"],
        expected_repository_tree=identity["tree"],
        expected_tasks_tree=identity["tasks_tree"],
        expected_dataset_manifest_blob=identity["dataset_manifest_blob"],
    )
    manifest = parse_terminal_dataset_manifest(
        (checkout / "tasks" / "dataset.toml").read_text(encoding="utf-8"),
        expected_count=int(identity["expected_task_count"]),
    )
    task_ids = tuple(name for name, _ in manifest.tasks)
    seal = seal_materialized_workload(
        family_id=row["family_id"],
        root=checkout / "tasks",
        task_ids=task_ids,
        expected_task_count=int(identity["expected_task_count"]),
    )
    authority = promote_materialized_verified(
        _source_authority(row),
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
    )
    return {
        "family_id": row["family_id"],
        "stage": authority.stage.name,
        "authority_digest": authority.digest,
        "source_authority_digest": row["authority_digest"],
        "git_identity": asdict(git_identity),
        "dataset_manifest": {
            "dataset_name": manifest.dataset_name,
            "task_count": manifest.task_count,
            "task_name_digest_manifest_sha256": manifest.canonical_task_digest,
        },
        "workload_seal": asdict(seal),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize and cryptographically verify the two preregistered DGC external workloads."
    )
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    output_root = Path(args.output_root).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("output-root must be absent or empty; refusing to mix evidence generations")
    output_root.mkdir(parents=True, exist_ok=True)

    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    rows = {row["family_id"]: row for row in registry["families"]}
    if set(rows) != {"SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"}:
        raise ValueError("external source registry must contain exactly the two frozen families")

    # Receipt is emitted only after both families reach MATERIALIZED_VERIFIED.
    swe = _materialize_swe(rows["SWE_BENCH_VERIFIED"], output_root)
    terminal = _materialize_terminal(rows["TERMINAL_BENCH_2_1"], output_root)
    receipt = {
        "schema": "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V1",
        "families": [swe, terminal],
        "execution_authorized": False,
        "product_promotion_authorized": False,
    }
    receipt_path = output_root / "MATERIALIZATION_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt": str(receipt_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
