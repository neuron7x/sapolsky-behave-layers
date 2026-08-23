from __future__ import annotations

from pathlib import Path

from cwc.governance.evidence_bundle import verify_evidence_bundle

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts/dgc-product-v1"


def main() -> int:
    result = verify_evidence_bundle(BUNDLE)
    print(f"DGC-PRODUCT-BUNDLE-COMPLETE: {str(result.complete).lower()}")
    if result.missing_files:
        print("DGC-PRODUCT-BUNDLE-MISSING: " + ",".join(result.missing_files))
    if result.unhashed_files:
        print("DGC-PRODUCT-BUNDLE-UNHASHED: " + ",".join(result.unhashed_files))
    if result.hash_mismatches:
        print("DGC-PRODUCT-BUNDLE-HASH-MISMATCH: " + ",".join(result.hash_mismatches))
    if not result.complete:
        print("DGC-PRODUCT-BUNDLE-GATE: FAIL")
        return 1
    print("DGC-PRODUCT-BUNDLE-GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
