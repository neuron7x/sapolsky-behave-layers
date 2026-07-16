"""Package a CWC WP-1 instrumentation run directory into a single self-verifying
zip archive (manifest, config, metrics, summary, overhead report, energy raw
samples, audit artifacts, SHA256SUMS all included as-is).

    python scripts/export_cwc_instrumentation_bundle.py --input artifacts/instrumentation/<run_id>
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


def verify_existing_checksums(run_dir: Path) -> list[str]:
    sums_path = run_dir / "SHA256SUMS"
    if not sums_path.exists():
        return [f"missing SHA256SUMS in {run_dir}; run compute_checksums() before exporting"]
    errors = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, relative = line.partition("  ")
        target = run_dir / relative
        if not target.exists():
            errors.append(f"SHA256SUMS references missing file: {relative}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(f"checksum mismatch for {relative}: expected {digest}, got {actual}")
    return errors


def export_bundle(run_dir: Path, output_path: Path) -> Path:
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(run_dir.parent)))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="instrumentation run directory")
    parser.add_argument("--output", type=Path, default=None, help="output zip path (default: <input>.zip)")
    parser.add_argument("--skip-checksum-verify", action="store_true")
    args = parser.parse_args()

    run_dir = args.input
    if not run_dir.is_dir():
        raise SystemExit(f"not a directory: {run_dir}")

    if not args.skip_checksum_verify:
        errors = verify_existing_checksums(run_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)

    output_path = args.output or run_dir.with_suffix(".zip")
    export_bundle(run_dir, output_path)
    print(f"EXPORT_PASS: {output_path}")


if __name__ == "__main__":
    main()
