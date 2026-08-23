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
from cwc.governance.materialization_transaction import AtomicEvidenceGeneration, sha256_file
from cwc.governance.workload_seal import seal_materialized_workload

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"


def _run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _capture(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo_identity(root: Path) -> tuple[str, str]:
    commit = _capture("git", "-C", str(root), "rev-parse", "HEAD")
    tree = _capture("git", "-C", str(root), "rev-parse", "HEAD^{tree}")
    dirty = _capture("git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise RuntimeError("repository must be clean before evidence materialization")
    return commit, tree


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "DGC-external-materializer/2"})
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
    # Git metadata was used for identity verification and is not workload payload.
    # Removing it makes the published generation independent of clone-local pack/log state.
    shutil.rmtree(checkout / ".git")
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
        description="Atomically materialize and cryptographically verify the two preregistered DGC external workloads."
    )
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    output_root = Path(args.output_root).resolve()
    if output_root.exists():
        raise ValueError("output-root must not exist; evidence generations are immutable")

    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    rows = {row["family_id"]: row for row in registry["families"]}
    if set(rows) != {"SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"}:
        raise ValueError("external source registry must contain exactly the two frozen families")

    repo_commit, repo_tree = _repo_identity(ROOT)
    source_registry_sha256 = sha256_file(SOURCE_REGISTRY)
    materializer_sha256 = sha256_file(Path(__file__).resolve())

    with AtomicEvidenceGeneration(output_root) as transaction:
        assert transaction.staging_root is not None
        swe = _materialize_swe(rows["SWE_BENCH_VERIFIED"], transaction.staging_root)
        terminal = _materialize_terminal(rows["TERMINAL_BENCH_2_1"], transaction.staging_root)
        receipt = {
            "schema": "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2",
            "families": [swe, terminal],
            "source_registry_sha256": source_registry_sha256,
            "repository_commit": repo_commit,
            "repository_tree": repo_tree,
            "materializer_sha256": materializer_sha256,
            "execution_authorized": False,
            "product_promotion_authorized": False,
        }
        provenance = {
            "schema": "DGC_MATERIALIZATION_PROVENANCE_V1",
            "claim": "VERIFIED_MATERIALIZATION_ONLY",
            "repository": {
                "git_commit": repo_commit,
                "git_tree": repo_tree,
            },
            "materials": {
                "external_source_registry_sha256": source_registry_sha256,
                "materializer_sha256": materializer_sha256,
                "source_authority_digests": sorted(row["authority_digest"] for row in rows.values()),
            },
            "slsa_conformance_claim": False,
            "execution_authorized": False,
            "product_promotion_authorized": False,
        }
        published = transaction.publish(receipt=receipt, provenance=provenance)

    print(
        json.dumps(
            {
                "status": "PASS",
                "receipt": str(output_root / AtomicEvidenceGeneration.RECEIPT_NAME),
                "payload_manifest_sha256": published.payload_manifest_sha256,
                "publication_manifest_sha256": published.publication_manifest_sha256,
                "file_count": published.file_count,
                "execution_authorized": False,
                "product_promotion_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
