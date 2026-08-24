from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

from cwc.governance.product_qualification_pointer import (
    CANONICAL_POINTER_PATH,
    ProductQualificationPointerError,
    verify_product_qualification_pointer,
)

CRITICAL_PATHS = (
    "artifacts/dgc-product-v1/evidence_status.json",
    "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V1.json",
    "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V1.json",
    "research/registry/dgc_math_proof_ledger_v1.json",
    ".github/workflows/dgc-math.yml",
    ".github/workflows/dgc-product-evidence.yml",
    "SBOM.spdx.json",
    "CITATION.cff",
)

PRODUCT_FIELDS = (
    "claim_frozen", "metrics_frozen", "baselines_frozen", "harness_frozen",
    "statistical_plan_frozen", "synthetic_mechanism_supported",
    "external_real_workload_supported", "quality_noninferiority_supported",
    "catastrophic_regret_noninferiority_supported", "coverage_equivalence_supported",
    "physical_cost_accounting_verified", "net_cost_superiority_supported",
    "generalization_supported", "fault_tolerance_supported",
    "independent_replication_supported", "evidence_bundle_complete",
    "production_provider_trace_supported", "shadow_mode_qualified", "bounded_canary_qualified",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(root: Path, *args: str, text: bool = True):
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return proc.stdout.strip() if text else proc.stdout


def tracked_paths(root: Path) -> tuple[Path, ...]:
    raw = _git(root, "ls-files", "-z", text=False)
    names = [part.decode("utf-8") for part in raw.split(b"\0") if part]
    paths = tuple(root / name for name in sorted(names))
    missing = [str(path.relative_to(root)) for path in paths if not path.exists() and not path.is_symlink()]
    if missing:
        raise RuntimeError(f"tracked files missing from checkout: {missing[:10]}")
    return paths


def _normalized_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if (info.mode & 0o111) else 0o644
    return info


def deterministic_tar_gz(root: Path, files: tuple[Path, ...], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in files:
                    archive.add(
                        path,
                        arcname=path.relative_to(root).as_posix(),
                        recursive=False,
                        filter=_normalized_filter,
                    )
    return sha256_file(destination)


def _load_evidence_status_mirror(root: Path) -> dict[str, object]:
    status_path = root / "artifacts/dgc-product-v1/evidence_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    missing = [field for field in PRODUCT_FIELDS if field not in status or not isinstance(status[field], bool)]
    if missing:
        raise RuntimeError(f"invalid DGC evidence status fields: {missing}")
    return status


def build_release(
    root: Path,
    out: Path,
    *,
    require_clean: bool = True,
    require_product_qualified: bool = False,
) -> dict:
    root = root.resolve()
    out = out.resolve()
    if require_clean:
        dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            raise RuntimeError("tracked working tree must be clean for DGC release")
    commit = _git(root, "rev-parse", "HEAD").lower()
    tree = _git(root, "rev-parse", "HEAD^{tree}").lower()
    files = tracked_paths(root)
    evidence_files = tuple(path for path in files if path.relative_to(root).as_posix().startswith("artifacts/"))
    evidence_set = set(evidence_files)
    source_files = tuple(path for path in files if path not in evidence_set)
    if not source_files or not evidence_files:
        raise RuntimeError("release requires both tracked source and tracked evidence populations")

    status = _load_evidence_status_mirror(root)
    qualification = None
    qualification_error = None
    try:
        qualification = verify_product_qualification_pointer(
            repository_root=root,
            pointer_path=Path(CANONICAL_POINTER_PATH),
            expected_repo_commit=commit,
            expected_repo_tree=tree,
        )
    except ProductQualificationPointerError as exc:
        qualification_error = str(exc)
    product_qualified = qualification is not None
    if require_product_qualified and not product_qualified:
        raise RuntimeError(f"PRODUCT_QUALIFIED requires terminal ledger/Global-V4 replay: {qualification_error}")

    # Production control is intentionally not inferred from evidence_status.json.
    # It requires a separate future operational authority and remains false here.
    production_control_authorized = False

    out.mkdir(parents=True, exist_ok=True)
    source_name = f"dgc-source-{commit[:12]}.tar.gz"
    evidence_name = f"dgc-evidence-{commit[:12]}.tar.gz"
    source_sha = deterministic_tar_gz(root, source_files, out / source_name)
    evidence_sha = deterministic_tar_gz(root, evidence_files, out / evidence_name)

    critical = {}
    for rel in CRITICAL_PATHS:
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f"critical release authority missing: {rel}")
        critical[rel] = sha256_file(path)

    qualification_record = None
    if qualification is not None:
        qualification_record = {
            "pointer_digest": qualification.pointer_digest,
            "generation_id": qualification.generation_id,
            "ledger_path": qualification.ledger_path,
            "ledger_sha256": qualification.ledger_sha256,
            "ledger_tip_receipt_digest": qualification.ledger_tip_receipt_digest,
            "global_v4_authority_path": qualification.global_v4_authority_path,
            "global_v4_authority_sha256": qualification.global_v4_authority_sha256,
            "global_v4_authority_digest": qualification.global_v4_authority_digest,
        }

    manifest = {
        "schema": "DGC_DETERMINISTIC_RESEARCH_RELEASE_V2",
        "git_commit": commit,
        "git_tree": tree,
        "release_authority": (
            "PRODUCT_QUALIFIED_LEDGER_GLOBAL_V4"
            if product_qualified
            else "RESEARCH_RELEASE_NOT_PRODUCT_QUALIFIED"
        ),
        "product_qualified": product_qualified,
        "production_control_authorized": production_control_authorized,
        "qualification_authority": qualification_record,
        "qualification_pointer_required_for_product_claim": True,
        "evidence_status_is_authority": False,
        "source_archive": {"name": source_name, "sha256": source_sha, "tracked_files": len(source_files)},
        "evidence_archive": {"name": evidence_name, "sha256": evidence_sha, "tracked_files": len(evidence_files)},
        "critical_authority_sha256": critical,
        "evidence_status_mirror": {
            "schema": status.get("schema"),
            "status": status.get("status"),
            "generated_on": status.get("generated_on"),
            "mirror_product_qualified": all(
                status.get(field) is True
                for field in (
                    "claim_frozen", "metrics_frozen", "baselines_frozen", "harness_frozen",
                    "statistical_plan_frozen", "external_real_workload_supported",
                    "quality_noninferiority_supported", "catastrophic_regret_noninferiority_supported",
                    "coverage_equivalence_supported", "physical_cost_accounting_verified",
                    "net_cost_superiority_supported", "generalization_supported", "fault_tolerance_supported",
                    "independent_replication_supported", "evidence_bundle_complete",
                )
            ),
        },
        "historical_root_release_manifest_is_current_dgc_authority": False,
        "notes": [
            "Archive contents are exactly tracked Git files split into source/non-artifacts and evidence/artifacts.",
            "gzip/tar metadata are normalized for deterministic rebuilds.",
            "PRODUCT_QUALIFIED is derived only from the canonical qualification pointer replaying the terminal ledger and Global V4 authority.",
            "evidence_status.json is an informational mirror and cannot authorize a product-qualified release.",
            "PRODUCT_QUALIFIED does not imply production control authority; provider trace, shadow and canary remain separate gates.",
            "No product or production authority is implied when product_qualified=false.",
        ],
    }
    manifest_path = out / "DGC_RELEASE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sum_paths = (out / source_name, out / evidence_name, manifest_path)
    sums = "\n".join(
        f"{sha256_file(path)}  {path.name}" for path in sorted(sum_paths, key=lambda path: path.name)
    ) + "\n"
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--require-product-qualified", action="store_true")
    args = parser.parse_args()
    manifest = build_release(
        args.root,
        args.out,
        require_clean=not args.allow_dirty,
        require_product_qualified=args.require_product_qualified,
    )
    print(
        "DGC-RELEASE-BUILD: PASS "
        f"commit={manifest['git_commit']} tree={manifest['git_tree']} "
        f"authority={manifest['release_authority']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
