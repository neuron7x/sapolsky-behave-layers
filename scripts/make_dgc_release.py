from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

from cwc.governance.deterministic_git_snapshot import create_deterministic_git_snapshot
from cwc.governance.qualified_evidence_bundle import build_qualified_evidence_bundle_authority

CRITICAL_PATHS = (
    "artifacts/dgc-product-v1/evidence_status.json",
    "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V2.json",
    "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
    "research/registry/dgc_math_proof_ledger_v1.json",
    ".github/workflows/dgc-math.yml",
    ".github/workflows/dgc-product-evidence.yml",
    "SBOM.spdx.json",
    "CITATION.cff",
)

EVIDENCE_PREFIXES = (
    "artifacts/",
    "eval_bundle/",
    "release_evidence/",
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


def tracked_paths_at_commit(root: Path, commit: str) -> tuple[str, ...]:
    raw = _git(root, "ls-tree", "-r", "--name-only", "-z", commit, text=False)
    return tuple(sorted(part.decode("utf-8") for part in raw.split(b"\0") if part))


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
                    if path.is_symlink():
                        raise RuntimeError(f"packaging evidence symlink rejected: {path.relative_to(root)}")
                    if not path.is_file():
                        raise RuntimeError(f"packaging evidence path is not a regular file: {path.relative_to(root)}")
                    archive.add(
                        path,
                        arcname=path.relative_to(root).as_posix(),
                        recursive=False,
                        filter=_normalized_filter,
                    )
    return sha256_file(destination)


def deterministic_git_archive_gz(root: Path, commit: str, destination: Path) -> str:
    """Create a normalized archive directly from immutable Git objects."""
    snapshot = create_deterministic_git_snapshot(
        repository_root=root,
        commit=commit,
        destination=destination,
    )
    return snapshot.archive_sha256


def _load_evidence_status_mirror(root: Path) -> dict[str, object]:
    status_path = root / "artifacts/dgc-product-v1/evidence_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    missing = [field for field in PRODUCT_FIELDS if field not in status or not isinstance(status[field], bool)]
    if missing:
        raise RuntimeError(f"invalid DGC evidence status fields: {missing}")
    return status


def _is_evidence_path(root: Path, path: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(rel.startswith(prefix) for prefix in EVIDENCE_PREFIXES)


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

    packaging_commit = _git(root, "rev-parse", "HEAD").lower()
    packaging_tree = _git(root, "rev-parse", "HEAD^{tree}").lower()
    files = tracked_paths(root)
    evidence_files = tuple(path for path in files if _is_evidence_path(root, path))
    if not evidence_files:
        raise RuntimeError("release requires a tracked evidence/metadata population")

    status = _load_evidence_status_mirror(root)
    qualification = None
    packaging_authority = None
    qualified_bundle = None
    qualification_error = None
    try:
        qualification, packaging_authority, qualified_bundle = build_qualified_evidence_bundle_authority(
            repository_root=root,
        )
    except RuntimeError as exc:
        qualification_error = str(exc)

    product_qualified = all(item is not None for item in (qualification, packaging_authority, qualified_bundle))
    if require_product_qualified and not product_qualified:
        raise RuntimeError(
            "PRODUCT_QUALIFIED requires terminal Global-V4 replay, append-only T_exec→T_pkg authority, "
            f"and graph-derived qualified evidence bundle: {qualification_error}"
        )

    production_control_authorized = False
    execution_commit = qualification.repo_commit if qualification is not None else packaging_commit
    execution_tree = qualification.repo_tree if qualification is not None else packaging_tree
    execution_files = tracked_paths_at_commit(root, execution_commit)
    if not execution_files:
        raise RuntimeError("execution source revision contains no tracked files")

    out.mkdir(parents=True, exist_ok=True)
    source_name = f"dgc-execution-source-{execution_commit[:12]}.tar.gz"
    evidence_name = f"dgc-packaging-evidence-{packaging_commit[:12]}.tar.gz"
    source_sha = deterministic_git_archive_gz(root, execution_commit, out / source_name)
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
            "qualified_execution_commit": qualification.repo_commit,
            "qualified_execution_tree": qualification.repo_tree,
            "ledger_path": qualification.ledger_path,
            "ledger_sha256": qualification.ledger_sha256,
            "ledger_tip_receipt_digest": qualification.ledger_tip_receipt_digest,
            "global_v4_authority_path": qualification.global_v4_authority_path,
            "global_v4_authority_sha256": qualification.global_v4_authority_sha256,
            "global_v4_authority_digest": qualification.global_v4_authority_digest,
        }

    packaging_record = packaging_authority.document if packaging_authority is not None else None
    bundle_record = qualified_bundle.document if qualified_bundle is not None else None

    manifest = {
        "schema": "DGC_DETERMINISTIC_RESEARCH_RELEASE_V4",
        "qualified_execution_source_commit": execution_commit,
        "qualified_execution_source_tree": execution_tree,
        "evidence_packaging_commit": packaging_commit,
        "evidence_packaging_tree": packaging_tree,
        "execution_source_identity_equals_packaging_identity": (
            execution_commit == packaging_commit and execution_tree == packaging_tree
        ),
        "release_authority": (
            "PRODUCT_QUALIFIED_T0_T1_GRAPH_COMPLETE_V1"
            if product_qualified
            else "RESEARCH_RELEASE_NOT_PRODUCT_QUALIFIED"
        ),
        "product_qualified": product_qualified,
        "production_control_authorized": production_control_authorized,
        "qualification_authority": qualification_record,
        "evidence_packaging_authority": packaging_record,
        "qualified_evidence_bundle_authority": bundle_record,
        "qualification_pointer_required_for_product_claim": True,
        "append_only_packaging_authority_required_for_product_claim": True,
        "graph_derived_bundle_authority_required_for_product_claim": True,
        "evidence_status_is_authority": False,
        "execution_source_archive": {
            "name": source_name,
            "sha256": source_sha,
            "git_tracked_files": len(execution_files),
            "source_commit": execution_commit,
            "source_tree": execution_tree,
        },
        "packaging_evidence_archive": {
            "name": evidence_name,
            "sha256": evidence_sha,
            "tracked_files": len(evidence_files),
            "packaging_commit": packaging_commit,
            "packaging_tree": packaging_tree,
        },
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
        "slsa_conformance_claim": False,
        "historical_root_release_manifest_is_current_dgc_authority": False,
        "notes": [
            "The execution-source archive is generated from immutable qualified revision T_exec, not packaging HEAD.",
            "T_pkg may differ from T_exec only under DGC_APPEND_ONLY_POST_OUTCOME_PACKAGING_POLICY_V1.",
            "The qualified bundle manifest is derived from the actual Pointer/P19/Global-V4 evidence graph, not a fixed filename checklist.",
            "Every required graph subject must be Git-bound either to T_exec or append-only evidence in T_pkg.",
            "Executable/statistical/scorer/policy mutation after T_exec makes product-qualified packaging fail closed.",
            "Source tar metadata are generated directly from Git objects with normalized UID/GID/mtime/modes; gitlinks and escaping symlinks are rejected.",
            "Packaging evidence archives reject symlinks and non-regular files.",
            "evidence_status.json is informational only and cannot authorize product qualification.",
            "PRODUCT_QUALIFIED does not imply production control authority; provider trace, shadow and canary remain separate gates.",
            "No SLSA conformance level is claimed by this custom provenance authority.",
        ],
    }

    packaging_authority_path = out / "DGC_EVIDENCE_PACKAGING_AUTHORITY.json"
    packaging_authority_path.write_text(
        json.dumps(packaging_record, indent=2, sort_keys=True) + "\n" if packaging_record is not None
        else json.dumps({"schema": "DGC_EVIDENCE_PACKAGING_AUTHORITY_NONE", "product_qualified": False}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    qualified_bundle_path = out / "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY.json"
    qualified_bundle_path.write_text(
        json.dumps(bundle_record, indent=2, sort_keys=True) + "\n" if bundle_record is not None
        else json.dumps({"schema": "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_NONE", "product_qualified": False}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = out / "DGC_RELEASE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sum_paths = (
        out / source_name,
        out / evidence_name,
        packaging_authority_path,
        qualified_bundle_path,
        manifest_path,
    )
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
        f"execution={manifest['qualified_execution_source_commit']} "
        f"packaging={manifest['evidence_packaging_commit']} "
        f"authority={manifest['release_authority']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
